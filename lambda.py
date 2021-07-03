import todoist, pymysql, os, logging
from datetime import datetime
logging.getLogger().setLevel(logging.INFO)

def error(error_msg: str, code: int) -> dict:
    logging.error(error_msg, exc_info=True)
    return {
            'statusCode': code,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': error_msg
    }

def get_access_token(user_id: str) -> str:
    
    #rds settings
    rds_host  = os.environ['RDS_ENDPOINT']
    username = os.environ['RDS_USERNAME']
    password = os.environ['RDS_PASSWORD']
    db_name = os.environ['RDS_DBNAME']
    
    try:
        rds = pymysql.connect(host=rds_host, user=username, passwd=password, db=db_name, connect_timeout=5)
    except pymysql.MySQLError as e:
        error('ERROR: Unexpected error: Could not connect to MySQL instance.', 500)
    
    cursor = rds.cursor()
    cursor.execute(f'select * from client_bearer.default where ID =\'{user_id}\'')
    results = cursor.fetchone()
    cursor.close()
    rds.close()
    
    try:
        access_token = results[1]
        return access_token
    except:
        error('ERROR: Unexpected error: Could not connect to MySQL instance.', 500)

def lambda_handler(event, context):

    ''' Can't add label if user isn't premium '''
    if event['initiator']['is_premium']:
        
        content = event['event_data']['content']
        user_id = event['event_data']['user_id']
        task_id = int(event['event_data']['id'])
        event_name = event['event_name']
        date_added = event['event_data']['date_added'][0:10]
        due_date = event['event_data']['due']['date']
        procrastinated_days = (datetime.strptime(due_date, '%Y-%m-%d') - datetime.strptime(date_added,'%Y-%m-%d')).days
        procrastinated_label = f'拖延了{procrastinated_days}天'

        ''' Add label to task only when it is updated due to procrastinating '''
        ''' Check if label exists because adding label will trigger this lambda function twice '''
        if event_name == 'item:updated':
            if date_added != due_date and procrastinated_label not in event['event_data']['labels']:

                # access_token = get_access_token(user_id)
                access_token = os.environ['TODOIST_ACCESS_TOKEN']

                if access_token is not None:    
                    api = todoist.TodoistAPI(access_token)
                    api.sync()
                    task = api.items.get_by_id(task_id)
                    
                    ''' Check if item due date is created originally in the future '''
                    notes = [notes['content'] for notes in api.state['notes'] if notes['item_id'] == task_id]
                    for note in notes:
                        if 'Procrastinator' in note:
                            date_added = note[23:33] # Use fixed length here rather than regex for performance, since note is created by us
                            procrastinated_days = (datetime.strptime(due_date, '%Y-%m-%d') - datetime.strptime(date_added,'%Y-%m-%d')).days
                            procrastinated_label = f'拖延了{procrastinated_days}天'
                            break

                    ''' Check again '''
                    if date_added != due_date and procrastinated_label not in request.json['event_data']['labels']:

                        ''' Create procrastinated label if not found in all labels '''
                        if not any(procrastinated_label in labels['name'] for labels in api.state['labels']):
                            api.labels.add(procrastinated_label)
                            api.commit()
                        
                        ''' Get all procrastinated label id (Reduces time complexity by searching only once) '''
                        procrastinated_dict = {}
                        for labels in api.state['labels']:
                            if '拖延' in labels['name']:
                                procrastinated_dict[labels['name']]=labels['id']
                
                        ''' Add procrastinating label to the front of task's original labels '''
                        if procrastinated_dict[procrastinated_label] not in task['labels']:
                            task_labels = task['labels']
                            for label in task_labels:
                                if label in procrastinated_dict.values():
                                    task_labels.remove(label) # Remove previous procrastinating label if exists
                            task_labels.insert(0, procrastinated_dict[procrastinated_label])
                            task.update(labels=task_labels)
                            api.commit()
                            status = f'Added {procrastinated_label}[{procrastinated_dict[procrastinated_label]}] to {task["content"]}'
                            logging.info(status)
                            return {
                                'statusCode': 200,
                                'headers': {
                                    'Content-Type': 'application/json'
                                },
                                'body': status
                            }

                    return {
                        'statusCode': 200,
                        'headers': {
                            'Content-Type': 'application/json'
                        },
                        'body': status
                    }
                else:
                    return error('ERROR: Unexpected error: Could not connect to MySQL instance.', 500)
        
        if event_name == 'item:added':
            if date_added != due_date:
                access_token = os.environ['TODOIST_ACCESS_TOKEN']
                api = todoist.TodoistAPI(access_token)
                api.sync()
                
                notes = [notes['content'] for notes in api.state['notes'] if notes['item_id'] == item_id]
                
                if not any('Procrastinator' in note for note in notes):
                    _ = api.notes.add(item_id, f'_ __[Procrastinator]__ {due_date} created_')
                    logger.info(f'Added Note[{due_date} created] to {item_content}')
                    api.commit()
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Content-Type': 'application/json'
                        },
                        'body': f'Added Note[{due_date} created] to {item_content}'
                    }
                else:
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Content-Type': 'application/json'
                        },
                        'body': ''
                    }
        
    else:
        return error('User not premium', 400)