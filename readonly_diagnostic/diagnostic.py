"""Isolated read-only Keep/Notion diagnostic. Never imports keep2notion.
No live execution entrypoint: inject an audited transport explicitly.
Only aggregate integers and fixed status labels may leave diagnose().
"""
import re

class DiagnosticError(Exception):
    pass

def normalized_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})', value):
        raise DiagnosticError('invalid_configuration')
    return value.replace('-', '').lower()


def validate_request(database_id, method, url, headers):
    base = f'https://api.notion.com/v1/databases/{database_id}'
    keep_login = method == 'POST' and url == 'https://api.gotokeep.com/v1.1/users/login'
    keep_list = method == 'GET' and re.fullmatch(r'https://api\.gotokeep\.com/pd/v3/stats/detail\?dateUnit=all&type=all&lastDate=[0-9]+', url)
    notion = (method == 'GET' and url == base) or (method == 'POST' and url == base + '/query')
    if not (keep_login or keep_list or notion):
        raise DiagnosticError('blocked_request')
    allowed_headers = set() if keep_login else ({'Authorization', 'Notion-Version'} if notion else {'Authorization'})
    if set(headers) != allowed_headers or any(not isinstance(v, str) or '\r' in v or '\n' in v for v in headers.values()):
        raise DiagnosticError('blocked_headers')
    if notion and headers['Notion-Version'] != '2022-06-28':
        raise DiagnosticError('blocked_headers')


class ReadOnlyAPI:
    def __init__(self, transport, database_id, expected_parent_id):
        normalized_id(database_id)
        normalized_id(expected_parent_id)
        self.transport = transport
        self.database_id = database_id
        self.expected_parent_id = expected_parent_id

    def request(self, method, url, payload=None, headers=None):
        validate_request(self.database_id, method, url, headers or {})
        try:
            return self.transport(method, url, payload, headers or {})
        except Exception:
            raise DiagnosticError('request_failed') from None


def diagnose(api, mobile, password, notion_token, country_code='86', page_limit=100):
    try:
        if type(page_limit) is not int or not 1 <= page_limit <= 100:
            raise DiagnosticError('invalid_limit')
        metadata = api.request('GET', f'https://api.notion.com/v1/databases/{api.database_id}',
            headers={'Authorization': 'Bearer ' + notion_token, 'Notion-Version': '2022-06-28'})
        if (metadata['object'] != 'database' or normalized_id(metadata['id']) != normalized_id(api.database_id)
            or metadata.get('archived') is not False or metadata.get('in_trash', False)
            or metadata['parent'].get('type') != 'page_id'
            or normalized_id(metadata['parent']['page_id']) != normalized_id(api.expected_parent_id)
            or metadata['properties']['Id']['type'] != 'rich_text'):
            raise DiagnosticError('target_preflight_failed')
        existing, cursor, seen = set(), None, set()
        sample_id = None
        sample_checked = False
        for _ in range(page_limit):
            if cursor in seen:
                raise DiagnosticError('target_pagination_cycle')
            seen.add(cursor)
            payload = {'page_size': 100, 'sorts': [{'timestamp': 'last_edited_time', 'direction': 'descending'}]}
            if cursor:
                payload['start_cursor'] = cursor
            body = api.request('POST', f'https://api.notion.com/v1/databases/{api.database_id}/query', payload,
                               {'Authorization': 'Bearer ' + notion_token, 'Notion-Version': '2022-06-28'})
            for item in body['results']:
                prop = item['properties'].get('Id')
                if not prop:
                    raise DiagnosticError('invalid_target_schema')
                values = prop['rich_text']
                identifier = ''.join(v['plain_text'] for v in values)
                if not sample_checked:
                    sample_checked = True
                    sample_id = identifier or None
                if identifier:
                    existing.add(identifier)
            if type(body['has_more']) is not bool:
                raise DiagnosticError('invalid_target_schema')
            if body['has_more'] is False:
                break
            cursor = body['next_cursor']
            if not isinstance(cursor, str) or not cursor:
                raise DiagnosticError('invalid_target_schema')
        else:
            raise DiagnosticError('target_page_limit')
        login = api.request('POST', 'https://api.gotokeep.com/v1.1/users/login',
                            {'mobile': mobile, 'password': password, 'countryCode': country_code})
        token = login['data']['token']
        if not isinstance(token, str) or not token:
            raise DiagnosticError('invalid_login')
        source, doubtful, cursor, seen = set(), set(), 0, set()
        for _ in range(page_limit):
            if cursor in seen:
                raise DiagnosticError('source_pagination_cycle')
            seen.add(cursor)
            body = api.request('GET', 'https://api.gotokeep.com/pd/v3/stats/detail?dateUnit=all&type=all&lastDate=' + str(cursor),
                               headers={'Authorization': 'Bearer ' + token})['data']
            for record in body['records']:
                for log in record['logs']:
                    if log['type'] != 'stats':
                        continue
                    stats = log['stats']
                    identifier = stats['id']
                    if not isinstance(identifier, str) or not identifier:
                        raise DiagnosticError('invalid_source_schema')
                    source.add(identifier)
                    if stats.get('isDoubtful'):
                        doubtful.add(identifier)
            cursor = body['lastTimestamp']
            if type(cursor) is not int or cursor < 0:
                raise DiagnosticError('invalid_source_schema')
            if cursor == 0:
                break
        else:
            raise DiagnosticError('source_page_limit')
        return {'status': 'complete', 'latest_edited_sample': 'found' if sample_id is not None and sample_id in source else 'unknown', 'source_count': len(source), 'target_unique_count': len(existing),
                'candidate_missing_count': len(source-existing),
                'candidate_non_doubtful_count': len(source-existing-doubtful), 'doubtful_count': len(doubtful)}
    except Exception:
        # No exception messages, URLs, bodies, identifiers, dates, titles or tracebacks.
        return {'status': 'incomplete', 'latest_edited_sample': 'unknown'}

class TLSJSONTransport:
    """Bounded stdlib-only transport. Constructing this class sends nothing.
    Use exclusively behind ReadOnlyAPI; no redirect, proxy, disk cache or logging.
    """
    def __init__(self, database_id):
        normalized_id(database_id)
        self.database_id = database_id
        import time
        self.deadline = time.monotonic() + 300
        import urllib.request
        import ssl
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def __call__(self, method, url, payload, headers):
        import json
        import urllib.parse
        import urllib.request
        validate_request(self.database_id, method, url, headers)
        import time
        if time.monotonic() >= self.deadline:
            raise DiagnosticError('deadline')
        request_headers = dict(headers)
        request_headers['User-Agent'] = 'readonly-sync-diagnostic/1'
        body = None
        if payload is not None:
            if url == 'https://api.gotokeep.com/v1.1/users/login':
                body = urllib.parse.urlencode(payload).encode()
                request_headers['Content-Type'] = 'application/x-www-form-urlencoded;charset=utf-8'
            else:
                body = json.dumps(payload).encode()
                request_headers['Content-Type'] = 'application/json'
        try:
            request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
            with self.opener.open(request, timeout=20) as response:
                if response.status != 200 or response.geturl() != url:
                    raise DiagnosticError('request_failed')
                chunks = []
                size = 0
                while size <= 2_000_000:
                    if time.monotonic() >= self.deadline:
                        raise DiagnosticError('deadline')
                    chunk = response.read1(min(65536, 2_000_001-size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                raw = b''.join(chunks)
                if len(raw) > 2_000_000:
                    raise DiagnosticError('response_limit')
                return json.loads(raw)
        except Exception:
            raise DiagnosticError('request_failed') from None
