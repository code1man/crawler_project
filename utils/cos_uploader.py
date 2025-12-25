from qcloud_cos import CosConfig, CosS3Client
from config import Config
import io

# 配置


# 初始化 client
cos_config = CosConfig(Region=REGION, SecretId=SECRET_ID, SecretKey=SECRET_KEY)
cos_client = CosS3Client(cos_config)

def upload_csv_to_cos(df, bucket, key, cos_client):
    """
    df: pandas.DataFrame
    bucket: 'examplebucket-1250000000'
    key: 'folder/filename.csv'
    cos_client: 已初始化的 CosS3Client
    """
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, encoding='utf-8-sig')
    buffer.seek(0)

    cos_client.put_object(
        Bucket=bucket,
        Body=buffer.getvalue(),
        Key=key,
        StorageClass='STANDARD',
        ContentType='text/csv'
    )

    # 返回 COS URL
    url = f"https://{bucket}.cos.{REGION}.myqcloud.com/{key}"
    return url
