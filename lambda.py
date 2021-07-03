import todoist, pymysql, os, logging
from datetime import datetime
from watched_events import ITEM
logging.getLogger().setLevel(logging.INFO)

def status_code(code, msg):
    if code != 200:
        logging.error(msg, exc_info=True)
    else:
        logging.info(msg, exc_info=True)
    return {
            'statusCode': code,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': msg
    }

def get_access_token(user_id: str):
    
    #rds settings
    rds_host  = os.environ['RDS_ENDPOINT']
    username = os.environ['RDS_USERNAME']
    password = os.environ['RDS_PASSWORD']
    db_name = os.environ['RDS_DBNAME']
    
    try:
        rds = pymysql.connect(host=rds_host, user=username, passwd=password, db=db_name, connect_timeout=5)
    except pymysql.MySQLError as e:
        status_code(500, 'ERROR: Unexpected error: Could not connect to MySQL instance.')
    
    cursor = rds.cursor()
    cursor.execute(f'select * from client_bearer.default where ID =\'{user_id}\'')
    results = cursor.fetchone()
    cursor.close()
    rds.close()
    
    try:
        access_token = results[1]
        return access_token
    except:
        status_code(500, 'ERROR: Unexpected error: Could not connect to MySQL instance.')

def lambda_handler(event, context):

    ''' Can't add label if user isn't premium '''
    if not event['initiator']['is_premium']:
        return status_code(400, 'User not premium')
    
    item_content = event['event_data']['content']
    #user_id = event['event_data']['user_id']
    item_id = int(event['event_data']['id'])
    event_name = event['event_name']
    date_added = event['event_data']['date_added'][0:10]
    due_date = event['event_data']['due']['date']
    procrastinated_days = (datetime.strptime(due_date, '%Y-%m-%d') - datetime.strptime(date_added,'%Y-%m-%d')).days
    procrastinated_label = f'拖延了{procrastinated_days}天'

    ''' Add label to task only when it is updated due to procrastinating '''
    ''' Check if label exists because adding label will trigger this lambda function twice '''
    if event_name == ITEM.UPDATED:
        if date_added != due_date and procrastinated_label not in event['event_data']['labels']:

            # access_token = get_access_token(user_id)
            access_token = os.environ['TODOIST_ACCESS_TOKEN']

            if access_token is None:
                return status_code(500, 'ERROR: Unexpected error: Could not connect to MySQL instance.')
            
            api = todoist.TodoistAPI(access_token)
            api.sync()
            item = api.items.get_by_id(item_id)
            
            ''' Check if item due date is created originally in the future '''
            for notes in api.state['notes']:
                if notes['item_id'] == item_id and 'Procrastinator' in notes['content']:
                    note = notes['content']
                    date_added = note[23:33] # Use fixed length here rather than regex for performance, since note is created by us
                    procrastinated_days = (datetime.strptime(due_date, '%Y-%m-%d') - datetime.strptime(date_added,'%Y-%m-%d')).days
                    procrastinated_label = f'拖延了{procrastinated_days}天'
                    break

            ''' Check again '''
            if date_added != due_date and procrastinated_label not in event['event_data']['labels']:

                ''' 1. Create procrastinated label if not found in all labels '''
                if not any(procrastinated_label in labels['name'] for labels in api.state['labels']):
                    api.labels.add(procrastinated_label)
                    api.commit()
                
                ''' 2. Get all procrastinated label id (Reduces time complexity by searching only once) '''
                procrastinated_dict = {}
                for labels in api.state['labels']:
                    if '拖延' in labels['name']:
                        procrastinated_dict[labels['name']]=labels['id']
        
                ''' 3. Add procrastinating label to the front of the item's original labels '''
                if procrastinated_dict[procrastinated_label] not in item['labels']:
                    item_labels = item['labels']
                    for label in item_labels:
                        if label in procrastinated_dict.values():
                            item_labels.remove(label) # Remove previous procrastinating label if exists
                            break
                    item_labels.insert(0, procrastinated_dict[procrastinated_label])
                    item.update(labels=item_labels)
                    api.commit()
                    status = f'Added {procrastinated_label}[{procrastinated_dict[procrastinated_label]}] to {item["content"]}'
                    logging.info(status)

        return status_code(200, '')
    
    ''' Consider items created for the future, fixes #1 '''
    if event_name == ITEM.ADDED:
        if date_added != due_date:

            access_token = os.environ['TODOIST_ACCESS_TOKEN']
            api = todoist.TodoistAPI(access_token)
            api.sync()
            
            # notes = [notes['content'] for notes in api.state['notes'] if notes['item_id'] == item_id]
            future_flag = False
            for notes in api.state['notes']:
                if notes['item_id'] == item_id and 'Procrastinator' in notes['content']:
                    future_flag = True
                    break
            
            if not future_flag:
                _ = api.notes.add(item_id, f'_ __[Procrastinator]__ {due_date} created_')
                logging.info(f'Added Note[{due_date} created] to {item_content}')
                api.commit()

        return status_code(200, '')