# Kafka Producer and Consumer Setup

## 1. Kafka Broker Address
- **Inside Docker:** `kafkaspark-kafka-1:9092`
- **From Host Machine:** `localhost:9092`

## 2. Running the Producer
Run the Kafka producer script to stream data in chunks (handling large files efficiently):
```bash
python3 kafka_producer.py
```

## 3. Consuming Messages
Consume messages from the raw data topic:
```bash
docker exec -it kafkaspark-kafka-1 kafka-console-consumer.sh --bootstrap-server kafkaspark-kafka-1:9092 --topic raw-vm-metrics --from-beginning
```

## 4. Monitoring Progress
The producer logs:
- Number of lines processed
- Number of records successfully sent
- Errors encountered

Useful commands:
```bash
docker exec -it kafkaspark-kafka-1 kafka-run-class.sh kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic raw-vm-metrics --time -1
docker exec -it kafkaspark-kafka-1 kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic raw-vm-metrics --from-beginning --max-messages 5

docker exec -it kafkaspark-kafka-1 kafka-run-class.sh kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic silver-vm-metrics --time -1
docker exec -it kafkaspark-kafka-1 kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic silver-vm-metrics --from-beginning --max-messages 5
```
