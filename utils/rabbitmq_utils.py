import pika
import json
from typing import Optional, Callable
from config.rabbitmq_config import rabbitmq_settings


class RabbitMQClient:
    def __init__(self):
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel = None

    def connect(self):
        credentials = pika.PlainCredentials(
            rabbitmq_settings.username,
            rabbitmq_settings.password
        )
        parameters = pika.ConnectionParameters(
            host=rabbitmq_settings.host,
            port=rabbitmq_settings.port,
            virtual_host=rabbitmq_settings.virtual_host,
            credentials=credentials
        )
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()

    def declare_queue(self, queue_name: str, durable: bool = True):
        if not self.channel:
            self.connect()
        self.channel.queue_declare(queue=queue_name, durable=durable)

    def publish(self, queue_name: str, message: dict):
        if not self.channel:
            self.connect()
        self.channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message, ensure_ascii=False),
            properties=pika.BasicProperties(
                delivery_mode=2
            )
        )

    def consume(self, queue_name: str, callback: Callable):
        if not self.channel:
            self.connect()
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=queue_name, on_message_callback=callback)
        self.channel.start_consuming()

    def close(self):
        if self.connection:
            self.connection.close()


mq_client = RabbitMQClient()
