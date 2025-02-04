Commands to run on a google CLI (local instance):
```
gcloud init
gcloud auth login
gcloud services enable compute.googleapis.com
```

```
terraform init
terraform apply

# Connect using SSH (Not required but helps with debugging)
gcloud compute instances list
gcloud compute ssh nordics-node --zone=europe-north1-a
gcloud compute ssh west-node --europe-west1-b

# Check if Cassandra installed correctly
gcloud compute ssh nordics-node --zone=europe-north1-a --command="dpkg -l | grep cassandra"

# If successful, proceed with configuration
NORDICS_IP=$(gcloud compute instances describe nordics-node --zone=europe-north1-a --format='get(networkInterfaces[0].networkIp)')
WEST_IP=$(gcloud compute instances describe eu-west-node --zone=europe-west1-b --format='get(networkInterfaces[0].networkIp)')

# Modify cassandra.yaml locally
sed -i "s/nordics-node-ip/$NORDICS_IP/g" cassandra.yaml
sed -i "s/asia-node-ip/$WEST_IP/g" cassandra.yaml

# Copy to nodes
gcloud compute scp cassandra.yaml nordics-node:/tmp/cassandra.yaml --zone=europe-north1-a
gcloud compute scp cassandra.yaml eu-west-node:/tmp/cassandra.yaml --zone=europe-west1-b

# Configure nodes
gcloud compute ssh nordics-node --zone=europe-north1-a --command="sudo cp /tmp/cassandra.yaml /etc/cassandra/cassandra.yaml && sudo systemctl restart cassandra"
gcloud compute ssh eu-west-node --zone=europe-west1-b --command="sudo cp /tmp/cassandra.yaml /etc/cassandra/cassandra.yaml && sudo systemctl restart cassandra"

terraform destroy
sudo systemctl status cassandra
```