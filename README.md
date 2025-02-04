Commands to run on a google CLI (local instance):
```
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

terraform destroy
sudo systemctl status cassandra
```
