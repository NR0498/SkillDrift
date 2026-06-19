from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from skilldrift.config import Settings, get_settings

logger = logging.getLogger(__name__)


def upload_run_summary(summary: dict[str, Any], settings: Settings | None = None) -> str | None:
    settings = settings or get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.aws_endpoint_url,
        region_name=settings.aws_region,
    )
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        create_args: dict[str, Any] = {"Bucket": settings.s3_bucket}
        if not settings.aws_endpoint_url and settings.aws_region != "us-east-1":
            create_args["CreateBucketConfiguration"] = {"LocationConstraint": settings.aws_region}
        client.create_bucket(**create_args)

    now = datetime.now(UTC)
    key = f"runs/{now:%Y/%m/%d}/{now:%H%M%S}-{now.microsecond:06d}/summary.json"
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=json.dumps(summary, indent=2).encode(),
        ContentType="application/json",
    )
    uri = f"s3://{settings.s3_bucket}/{key}"
    logger.info("Uploaded run summary to %s", uri)
    return uri
