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
    cursor.execute('select * from client_bearer.default where ID =\'{}\''.format(user_id))
    results = cursor.fetchone()
    cursor.close()
    rds.close()
    
    try:
        # auth_token = results[1]
        access_token = results[2]
        return access_token
    except:
        error('ERROR: Unexpected error: Could not connect to MySQL instance.', 500)

def lambda_handler(event, context):

    # Can't add label if user isn't premium
    if event['initiator']['is_premium']:
        
        user_id = event['event_data']['user_id']
        task_id = int(event['event_data']['id'])
        event_name = event['event_name']
        date_added = event['event_data']['date_added'][0:10]
        due_date = event['event_data']['due']['date']
        procrastinated_days = (datetime.strptime(due_date, '%Y-%m-%d') - datetime.strptime(date_added,'%Y-%m-%d')).days
        procrastinated_label = '拖延了{}天'.format(procrastinated_days)
        
        # Add label to task only when it is updated due to procrastinating
        # Check if label exists because adding label will trigger this lambda function twice
        if event_name == 'item:updated' and date_added != due_date and procrastinated_label not in event['event_data']['labels']:

            access_token = get_access_token(user_id)
                
            api = todoist.TodoistAPI(access_token)
            api.sync()
            task = api.items.get_by_id(task_id)
            
            # Create procrastinated label if not found in all labels
            if not any(procrastinated_label in labels['name'] for labels in api.state['labels']):
                api.labels.add(procrastinated_label)
                api.commit()
            
            # Get all procrastinated label id (Reduces time complexity by searching only once)
            procrastinated_dict = {}
            for labels in api.state['labels']:
                if '拖延' in labels['name']:
                    procrastinated_dict[labels['name']]=labels['id']
    
            # Add procrastinating label to the front of task's original labels
            if procrastinated_dict[procrastinated_label] not in task['labels']:
                task_labels = task['labels']
                for label in task_labels:
                    if label in procrastinated_dict.values():
                        task_labels.remove(label) # Remove previous procrastinating label if exists
                task_labels.insert(0, procrastinated_dict[procrastinated_label])
                task.update(labels=task_labels)
                api.commit()
                status = 'Added {}[{}] to {}'.format(procrastinated_label, procrastinated_dict[procrastinated_label], task['content'])
                logging.info(status)
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json'
                    },
                    'body': status
                }
        
    else:
        return error('User not premium', 400)