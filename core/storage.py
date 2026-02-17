import uuid
import boto3
from botocore.config import Config
import env


_client = None


def _get_client():
    global _client
    if _client is None:
        session = boto3.session.Session()
        _client = session.client(
            's3',
            region_name=env.DO_SPACES_REGION,
            endpoint_url=f'https://{env.DO_SPACES_REGION}.digitaloceanspaces.com',
            aws_access_key_id=env.DO_SPACES_ACCESS_KEY,
            aws_secret_access_key=env.DO_SPACES_SECRET_KEY,
            config=Config(s3={'addressing_style': 'virtual'}),
        )
    return _client


def upload_file(file_obj, remote_path, content_type='application/octet-stream'):
    """Upload a file to DO Spaces and return the CDN URL."""
    client = _get_client()
    full_path = f"{env.DO_SPACES_BASE_PATH}/{remote_path}"
    client.upload_fileobj(
        file_obj,
        env.DO_SPACES_NAME,
        full_path,
        ExtraArgs={'ACL': 'public-read', 'ContentType': content_type},
    )
    return f"{env.DO_SPACES_CDN_ENDPOINT}/{full_path}"
