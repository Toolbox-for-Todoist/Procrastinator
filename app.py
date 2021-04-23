import todoist, os
from datetime import datetime
from flask import Flask, request, Response
app = Flask(__name__)


@app.route('/', methods=['POST'])
def respond():
    api = todoist.TodoistAPI(os.environ['TODOIST_SECRET'])
    api.sync()
    id = int(request.json['event_data']['id'])
    event_name = request.json['event_name']
    date_added = request.json['event_data']['date_added'][0:10]
    due_date = request.json['event_data']['due']['date']
    
    # Triggered when due date is moved (will also be triggered when labels are added)
    if event_name == 'item:updated' and date_added != due_date:
        item = api.items.get_by_id(id)
        delay_str = '拖延了{}天'.format((datetime.strptime(due_date, '%Y-%m-%d') - datetime.strptime(date_added,'%Y-%m-%d')).days)

        # Create label if not found
        if not any(delay_str in labels['name'] for labels in api.state['labels']):
            api.labels.add(delay_str)
            api.commit()
        
        # Get all delay label id (Reduces time complexity to search only once)
        delay_dict = {}
        for labels in api.state['labels']:
            if '拖延' in labels['name']:
                delay_dict[labels['name']]=labels['id']

        # Add procrastinating label to the front of task's original labels
        if delay_dict[delay_str] not in item['labels']:
            labels = item['labels']
            for label in labels:
                if label in delay_dict.values():
                    labels.remove(label) # Remove previous delayed label if exists
            labels.insert(0, delay_dict[delay_str])
            item.update(labels=labels)
            api.commit()


    return Response(status=200)

if __name__ == '__main__':
    app.run()