Commands to run on a google CLI (local instance):
gcloud init
gcloud auth login
gcloud services enable compute.googleapis.com

git clone

terraform init
terraform apply

gcloud compute instances list
gcloud compute ssh nordics-node --zone=europe-north1-a
gcloud compute ssh west-node --europe-west1-b

gcloud compute scp cassandra.yaml nordics-node:/tmp/cassandra.yaml --zone=europe-north1-a
gcloud compute ssh nordics-node --zone=europe-north1-a
# Then on the VM:
sudo cp /tmp/cassandra.yaml /etc/cassandra/cassandra.yaml
sudo chown cassandra:cassandra /etc/cassandra/cassandra.yaml
seeds: '10.166.0.2, 10.0.0.2'  # Use internal IPs from your VM instances
sudo systemctl restart cassandra
sudo systemctl status cassandra
nodetool status
gcloud compute scp cassandra.yaml west-node:/tmp/cassandra.yaml --zone=europe-west1-b

terraform destroy
sudo systemctl status cassandra
