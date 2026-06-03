"""Azure Blob Storage client for publishing HTML reports.

Uploads HTML (and optionally Excel) files to a private Azure Blob Storage
container.  Access is controlled via Azure AD RBAC – no SAS tokens, no
expiry dates.  Employees need the 'Storage Blob Data Reader' role on the
container to view reports in their browser via the MSAL-protected index page.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_BLOB_URL = "https://{account}.blob.core.windows.net"


def _get_client(account: str, tenant_id: str, client_id: str, client_secret: str):
    """Return an authenticated BlobServiceClient using the Service Principal."""
    from azure.identity import ClientSecretCredential
    from azure.storage.blob import BlobServiceClient

    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )
    url = _BLOB_URL.format(account=account)
    return BlobServiceClient(account_url=url, credential=credential)


def upload_reports(
    account: str,
    container: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    files: list[str],
    progress_cb=None,
) -> list[str]:
    """Upload a list of local files to the blob container.

    Args:
        account:       Storage account name (e.g. 'costcenterreports')
        container:     Container name (e.g. 'reports')
        tenant_id:     Azure AD Tenant ID (reuse from cost queries)
        client_id:     Service Principal Client ID
        client_secret: Service Principal Client Secret
        files:         List of absolute local file paths to upload
        progress_cb:   Optional callable(message: str) for status updates

    Returns:
        List of blob URLs (without SAS – accessed via AD login).
    """
    client = _get_client(account, tenant_id, client_id, client_secret)
    container_client = client.get_container_client(container)

    # Create container if it doesn't exist yet
    try:
        container_client.create_container()
        logger.info("Container '%s' angelegt.", container)
    except Exception:
        pass  # already exists

    urls: list[str] = []
    for i, file_path in enumerate(files):
        path = Path(file_path)
        if not path.exists():
            logger.warning("Datei nicht gefunden, übersprungen: %s", file_path)
            continue

        blob_name = path.name
        content_type = "text/html" if path.suffix == ".html" else "application/octet-stream"

        if progress_cb:
            progress_cb(f"Lade hoch: {blob_name} …")
        logger.info("Upload: %s → %s/%s", path.name, container, blob_name)

        with open(path, "rb") as f:
            container_client.upload_blob(
                name=blob_name,
                data=f,
                overwrite=True,
                content_settings=_content_settings(content_type),
            )

        url = f"{_BLOB_URL.format(account=account)}/{container}/{blob_name}"
        urls.append(url)
        logger.info("  ✓ %s", url)

    return urls


def list_blobs(
    account: str,
    container: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> list[dict]:
    """Return list of blobs in the container with name and last_modified."""
    client = _get_client(account, tenant_id, client_id, client_secret)
    container_client = client.get_container_client(container)
    result = []
    try:
        for blob in container_client.list_blobs():
            result.append({
                "name":          blob.name,
                "last_modified": blob.last_modified,
                "size":          blob.size,
            })
    except Exception as exc:
        logger.error("Fehler beim Auflisten der Blobs: %s", exc)
    return sorted(result, key=lambda b: b["name"], reverse=True)


def _content_settings(content_type: str):
    from azure.storage.blob import ContentSettings
    return ContentSettings(content_type=content_type)
