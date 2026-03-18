"""
AWS Lambda WebSocket handler for Fresenius AI Assistant
Handles WebSocket connections via API Gateway WebSocket API
"""
import asyncio
import json
import os
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

import boto3
from dotenv import load_dotenv

load_dotenv()

from app.agent import create_session, run_agent, sessions, update_aws_credentials
from app.auth import verify_token
from app.database import setup_database, get_patient, get_patient_count

# Initialize database on cold start
setup_database()

# API Gateway Management API client - initialized per request
def get_apigw_client(domain, stage):
    """Create API Gateway Management API client for sending messages to WebSocket connections"""
    endpoint_url = f"https://{domain}/{stage}"
    return boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)

# Thread pool for async operations
_thread_pool = ThreadPoolExecutor(max_workers=10)

# Store connection metadata (in production, use DynamoDB)
# For Lambda, we'll use DynamoDB to persist connection state
dynamodb = boto3.resource('dynamodb')
connections_table_name = os.getenv('CONNECTIONS_TABLE', 'fresenius_websocket_connections')

def lambda_handler(event, context):
    """
    Handle WebSocket events from API Gateway

    Event types:
    - $connect: Client connects
    - $disconnect: Client disconnects
    - $default: Message from client
    """
    route_key = event.get('requestContext', {}).get('routeKey')
    connection_id = event.get('requestContext', {}).get('connectionId')
    domain_name = event.get('requestContext', {}).get('domainName')
    stage = event.get('requestContext', {}).get('stage')

    print(f"WebSocket event: route={route_key}, connection={connection_id}")

    if route_key == '$connect':
        return handle_connect(event, connection_id)
    elif route_key == '$disconnect':
        return handle_disconnect(event, connection_id)
    elif route_key == '$default':
        return handle_message(event, connection_id, domain_name, stage)

    return {'statusCode': 200}

def handle_connect(event, connection_id):
    """Handle new WebSocket connection"""
    # Verify authentication via query string (since WebSocket doesn't support cookies easily)
    query_params = event.get('queryStringParameters') or {}
    token = query_params.get('token')

    if not token or not verify_token(token):
        print(f"Authentication failed for connection {connection_id}")
        return {'statusCode': 401}

    print(f"Client connected: {connection_id}")
    return {'statusCode': 200}

def handle_disconnect(event, connection_id):
    """Handle WebSocket disconnection"""
    # Clean up session
    if connection_id in sessions:
        del sessions[connection_id]

    print(f"Client disconnected: {connection_id}")
    return {'statusCode': 200}

def handle_message(event, connection_id, domain_name, stage):
    """Handle incoming WebSocket message"""
    try:
        body = json.loads(event.get('body', '{}'))
        msg_type = body.get('type')

        apigw_client = get_apigw_client(domain_name, stage)

        if msg_type == 'init':
            return handle_init(body, connection_id, apigw_client)
        elif msg_type == 'message':
            return handle_chat_message(body, connection_id, apigw_client)

        return {'statusCode': 200}

    except Exception as e:
        print(f"Error handling message: {e}")
        traceback.print_exc()
        try:
            send_message(apigw_client, connection_id, {
                'type': 'error',
                'content': f'Server error: {str(e)}'
            })
        except:
            pass
        return {'statusCode': 500}

def handle_init(body, connection_id, apigw_client):
    """Initialize agent session"""
    role = body.get('role', 'patient').lower()
    patient_id_raw = body.get('patient_id')

    patient_info = None
    if role == 'patient':
        try:
            patient_id = int(patient_id_raw)
            total = get_patient_count()
            if patient_id < 1 or patient_id > total:
                raise ValueError
        except (TypeError, ValueError):
            send_message(apigw_client, connection_id, {
                'type': 'error',
                'content': f'Invalid Patient ID. Please enter a number between 1 and 112.'
            })
            return {'statusCode': 200}

        patient_info = get_patient(patient_id)
        if not patient_info:
            send_message(apigw_client, connection_id, {
                'type': 'error',
                'content': f'Patient {patient_id} not found in the database.'
            })
            return {'statusCode': 200}

    # Create session using connection_id as session_id
    try:
        create_session(connection_id, role, patient_info)
        send_message(apigw_client, connection_id, {
            'type': 'ready',
            'session_id': connection_id
        })
    except Exception as exc:
        send_message(apigw_client, connection_id, {
            'type': 'error',
            'content': f'Failed to initialize agent: {exc}'
        })

    return {'statusCode': 200}

def handle_chat_message(body, connection_id, apigw_client):
    """Handle chat message from client"""
    content = body.get('content', '').strip()
    if not content:
        return {'statusCode': 200}

    if connection_id not in sessions:
        send_message(apigw_client, connection_id, {
            'type': 'error',
            'content': 'Session not initialized. Please refresh the page.'
        })
        return {'statusCode': 200}

    # Send thinking indicator
    send_message(apigw_client, connection_id, {'type': 'thinking'})

    # Run agent in thread pool (Lambda will wait)
    try:
        result = run_agent(connection_id, content)
        send_message(apigw_client, connection_id, {
            'type': 'response',
            'content': result['output'],
            'steps': result['steps']
        })
    except Exception as exc:
        traceback.print_exc()
        send_message(apigw_client, connection_id, {
            'type': 'error',
            'content': f'Agent error: {exc}'
        })

    return {'statusCode': 200}

def send_message(apigw_client, connection_id, message):
    """Send message to WebSocket client"""
    try:
        apigw_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message).encode('utf-8')
        )
    except apigw_client.exceptions.GoneException:
        # Connection is closed
        print(f"Connection {connection_id} is gone")
        if connection_id in sessions:
            del sessions[connection_id]
    except Exception as e:
        print(f"Error sending message to {connection_id}: {e}")