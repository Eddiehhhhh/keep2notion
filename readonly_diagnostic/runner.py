"""Safe manual entrypoint, requires private fixed target configuration.
Not deployed. Never reads .env or imports upstream modules.
"""
import json
import os

def run():
    # No network until ALL required values and private target identifiers validate.
    from diagnostic import ReadOnlyAPI, TLSJSONTransport, diagnose, normalized_id
    names = ('NOTION_TOKEN', 'NOTION_PAGE', 'NOTION_WORKOUT_DATABASE_ID', 'KEEP_MOBILE', 'KEEP_PASSWORD')
    config = {name: os.environ.get(name, '') for name in names}
    if not all(config.values()):
        return {'status': 'configuration_unavailable'}
    target = config['NOTION_WORKOUT_DATABASE_ID']
    parent = config['NOTION_PAGE']
    normalized_id(target)
    normalized_id(parent)
    api = ReadOnlyAPI(TLSJSONTransport(target), target, parent)
    return diagnose(api, config['KEEP_MOBILE'], config['KEEP_PASSWORD'], config['NOTION_TOKEN'],
                    os.environ.get('COUNTRY_CODE') or '86')

if __name__ == '__main__':
    try:
        result = run()
    except BaseException:
        result = {'status': 'incomplete'}
    print(json.dumps(result, separators=(',', ':')))
    raise SystemExit(0 if result.get('status') == 'complete' else 1)
