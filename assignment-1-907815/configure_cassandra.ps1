# Retrieve IP addresses of Cassandra nodes
$NORDICS_IP = gcloud compute instances describe nordics-node --zone=europe-north1-a --format="get(networkInterfaces[0].networkIP)"
$WEST_IP = gcloud compute instances describe eu-west-node --zone=europe-west1-b --format="get(networkInterfaces[0].networkIP)"

# Confirm node creation and IP addresses
Write-Host "Nordics Node IP: $NORDICS_IP"
Write-Host "West Node IP: $WEST_IP"

# Modify cassandra.yaml configuration for Nordics node
$content = Get-Content -Path "cassandra.yaml"
$content = $content -replace "CURRENT_NODE_IP", $NORDICS_IP
$content = $content -replace "NORDICS_NODE_IP", $NORDICS_IP
$content = $content -replace "WEST_NODE_IP", $WEST_IP
$content | Set-Content -Path "cassandra_nordic.yaml"

# Modify cassandra.yaml configuration for West node
$content = Get-Content -Path "cassandra.yaml"
$content = $content -replace "CURRENT_NODE_IP", $WEST_IP
$content = $content -replace "NORDICS_NODE_IP", $NORDICS_IP
$content = $content -replace "WEST_NODE_IP", $WEST_IP
$content | Set-Content -Path "cassandra_west.yaml"

# Copy to nodes
gcloud compute scp cassandra_nordic.yaml nordics-node:/tmp/cassandra.yaml --zone=europe-north1-a
gcloud compute scp cassandra_west.yaml eu-west-node:/tmp/cassandra.yaml --zone=europe-west1-b

# Configure nodes and restart Cassandra
gcloud compute ssh nordics-node --zone=europe-north1-a --command="sudo cp /tmp/cassandra.yaml /etc/cassandra/cassandra.yaml && sudo systemctl restart cassandra"
gcloud compute ssh eu-west-node --zone=europe-west1-b --command="sudo cp /tmp/cassandra.yaml /etc/cassandra/cassandra.yaml && sudo systemctl restart cassandra"
