"""One-off verify script for new Cloudinary folder scheme."""
import io
import uuid
from urllib import request as urlrequest

import cloudinary
import cloudinary.api

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.enums import AttachmentEntityTypeEnum
from app.models.profile import Profile
from app.models.purchase_order import PurchaseOrder
from app.models.workspace import Workspace
from app.schemas.attachment import AttachmentSignRequest
from app.services.attachment_service import attachment_service

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)


def multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> tuple[str, bytes]:
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    body = io.BytesIO()
    for name, value in fields.items():
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.write(f"{value}\r\n".encode())
    for name, (filename, content, mime) in files.items():
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
        body.write(f"Content-Type: {mime}\r\n\r\n".encode())
        body.write(content)
        body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())
    return boundary, body.getvalue()


def main() -> None:
    db = SessionLocal()
    try:
        po = db.query(PurchaseOrder).order_by(PurchaseOrder.id.asc()).first()
        if not po:
            raise SystemExit("No purchase order found for verify")
        workspace = db.query(Workspace).filter(Workspace.id == po.workspace_id).first()
        user = db.query(Profile).filter(Profile.id == workspace.owner_user_id).first()
        print("PO", po.id, po.po_number, "workspace", workspace.name)

        payload = AttachmentSignRequest(
            entity_type=AttachmentEntityTypeEnum.PURCHASE_ORDER,
            entity_id=po.id,
            file_name="verify-upload.png",
            mime_type="image/png",
            file_size=68,
        )
        sign = attachment_service.sign_upload(db, workspace=workspace, user=user, payload=payload)
        print("sign public_id", sign.public_id)
        print("sign asset_folder", sign.asset_folder)
        print("sign display_name", sign.display_name)

        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789c6300010000050001"
            "0d0a2db4"
            "0000000049454e44ae426082"
        )
        fields = {
            "api_key": sign.api_key,
            "timestamp": str(sign.timestamp),
            "signature": sign.signature,
            "public_id": sign.public_id,
            "asset_folder": sign.asset_folder,
            "display_name": sign.display_name,
            "type": sign.type,
        }
        files = {"file": ("verify-upload.png", png, "image/png")}
        boundary, body = multipart(fields, files)
        req = urlrequest.Request(sign.upload_url, data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        with urlrequest.urlopen(req, timeout=30) as resp:
            print("cloudinary status", resp.status)

        confirmed = attachment_service.confirm_upload(
            db, workspace_id=workspace.id, attachment_id=sign.attachment_id
        )
        print("confirm status", confirmed.upload_status)
        print("thumb", confirmed.urls.thumb_url)

        resource = cloudinary.api.resource(
            sign.public_id,
            resource_type="image",
            type="authenticated",
        )
        print("admin public_id", resource.get("public_id"))
        print("admin asset_folder", resource.get("asset_folder"))
        print("admin display_name", resource.get("display_name"))

        assert "makorsha" not in sign.public_id
        assert "Purchase Orders" in sign.asset_folder
        assert po.po_number in sign.asset_folder
        assert workspace.name in sign.asset_folder
        assert sign.display_name == "verify-upload.png"
        assert sign.type == "authenticated"
        assert resource.get("asset_folder") == sign.asset_folder
        assert resource.get("display_name") == sign.display_name
        assert confirmed.urls.thumb_url is not None
        assert "/image/authenticated/s--" in confirmed.urls.thumb_url
        print("VERIFY_OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
