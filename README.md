# Huminahon
A data pipeline and machine learning project built on NASA Earth observation data. It measures how many days soil moisture takes to return to its seasonal normal after typhoons and heavy-rain floods, then predicts which areas stay waterlogged longest.

#Updates
*Checkpoint 1*
Started setting up AWS. Created an IAM group containing the poweruseraccess policy for all the users as builders. This does not allow them however to view billing and IAM. Also created a Budget under Billing with a monthly cap at $20. Lastly, created S3 bucket under us-west-2 region. This region was selected to retrieve the NASA dataset without having to download it directly, as compared to a closer region geographically to the Philippines. The bucket uses the default SSE3-S3 for encryption and Versioning is turned off for now.
