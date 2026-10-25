import asyncio
from functools import lru_cache
from typing import BinaryIO, Protocol

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from app.core.config import get_settings


class ObjectStorage(Protocol):
    async def upload(self, file_object: BinaryIO, key: str, content_type: str) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def get_bytes(self, key: str) -> bytes: ...

    async def put_bytes(self, data: bytes, key: str, content_type: str) -> None: ...

    async def create_presigned_get_url(self, key: str, filename: str) -> str: ...


class S3ObjectStorage:
    def __init__(
        self,
        client: BaseClient,
        presign_client: BaseClient,
        bucket: str,
        presigned_url_expiry_seconds: int,
    ) -> None:
        self._client = client
        self._presign_client = presign_client
        self._bucket = bucket
        self._presigned_url_expiry_seconds = presigned_url_expiry_seconds

    async def upload(self, file_object: BinaryIO, key: str, content_type: str) -> None:
        file_object.seek(0)
        await asyncio.to_thread(
            self._client.upload_fileobj,
            file_object,
            self._bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)

    async def get_bytes(self, key: str) -> bytes:
        response = await asyncio.to_thread(
            self._client.get_object, Bucket=self._bucket, Key=key
        )
        return await asyncio.to_thread(response["Body"].read)

    async def put_bytes(self, data: bytes, key: str, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def create_presigned_get_url(self, key: str, filename: str) -> str:
        safe_filename = filename.replace('"', "").replace("\r", "").replace("\n", "")
        return await asyncio.to_thread(
            self._presign_client.generate_presigned_url,
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ResponseContentDisposition": f'inline; filename="{safe_filename}"',
            },
            ExpiresIn=self._presigned_url_expiry_seconds,
        )


@lru_cache
def get_storage_service() -> ObjectStorage:
    settings = get_settings()
    client_kwargs: dict[str, object] = {
        "service_name": "s3",
        "region_name": settings.aws_region,
        "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    }
    if settings.s3_endpoint_url:
        client_kwargs["endpoint_url"] = settings.s3_endpoint_url
    if settings.aws_access_key_id:
        client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
    if settings.aws_secret_access_key:
        client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    client = boto3.client(**client_kwargs)
    presign_client = client
    if settings.s3_public_endpoint_url:
        presign_client_kwargs = {
            **client_kwargs,
            "endpoint_url": settings.s3_public_endpoint_url,
        }
        presign_client = boto3.client(**presign_client_kwargs)
    return S3ObjectStorage(
        client=client,
        presign_client=presign_client,
        bucket=settings.s3_bucket,
        presigned_url_expiry_seconds=settings.s3_presigned_url_expiry_seconds,
    )

