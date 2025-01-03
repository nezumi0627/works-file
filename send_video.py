"""Works Mobile APIクライアント - 動画アップロード用."""

import base64
import json
import logging
import os
import struct
import time
from typing import Dict, Union

import requests

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class VideoUploader:
    """動画ファイルアップロード処理を行うクラス."""

    def __init__(self, file_data: Union[bytes, str]) -> None:
        """初期化.

        Args:
            file_data (Union[bytes, str]): ファイルのバイナリデータまたはBase64

        Note:
            code=416, message="Filesize must be greater than 0"の場合は
            拡張子が対応外のファイルである可能性があります。
        """
        self.file_data = (
            base64.b64decode(file_data)
            if isinstance(file_data, str)
            else file_data
        )
        self.file_size = len(self.file_data)
        self.duration = self._get_mp4_duration()

    def _get_mp4_duration(self) -> float:
        """MP4ファイルの長さを取得.

        Returns:
            float: 動画の長さ（秒）
        """
        try:
            # mvhdボックスを探す
            mvhd_pos = bytes(self.file_data).find(b"mvhd")
            if mvhd_pos == -1:
                return 0.0

            # タイムスケールと継続時間を読み取る
            time_scale = struct.unpack(
                ">I", self.file_data[mvhd_pos + 16 : mvhd_pos + 20]
            )[0]
            duration = struct.unpack(
                ">I", self.file_data[mvhd_pos + 20 : mvhd_pos + 24]
            )[0]

            # 秒数を計算
            return duration / time_scale

        except Exception as e:
            logger.error("Failed to get video duration: %s", str(e))
            return 0.0


class WorksVideoAPI:
    """Works Mobile APIクライアント - 動画アップロード用.

    Works Mobile APIを使用して動画ファイルのアップロードを行うクラス.
    """

    def __init__(self, channel_no: str, caller_no: str) -> None:
        """初期化.

        Args:
            channel_no (str): チャンネル番号
            caller_no (str): 発信者番号

        cookiesファイルを読み込み、APIのベースURLを設定します。
        """
        self.base_url = "https://talk.worksmobile.com"
        self.storage_url = "https://storage.worksmobile.com"
        self.cookies = self._load_cookies()
        self.channel_no = channel_no
        self.caller_no = caller_no

    def _load_cookies(self) -> Dict[str, str]:
        """cookiesファイルを読み込む.

        Returns:
            Dict[str, str]: cookiesの辞書
        """
        with open("cookies.json", encoding="utf-8") as f:
            return json.load(f)

    def _get_common_headers(self) -> Dict[str, str]:
        """共通ヘッダーを取得.

        Returns:
            Dict[str, str]: 共通ヘッダーの辞書
        """
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "ja,en-US;q=0.9,en;q=0.8",
            "device-language": "ja_JP",
            "origin": "https://talk.worksmobile.com",
            "referer": "https://talk.worksmobile.com/",
            "sec-ch-ua": (
                '"Chromium";v="124", "Google Chrome";v="124", '
                '"Not-A.Brand";v="99"'
            ),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
        }

    def issue_resource_path(
        self,
        filename: str,
        file_data: Union[bytes, str],
        channel_no: int,
    ) -> Dict:
        """リソースパスを取得するAPI.

        Args:
            filename (str): アップロードするファイル名
            file_data (Union[bytes, str]): ファイルのバイナリデータまたはBase64
            channel_no (int): チャンネル番号

        Returns:
            Dict: リソースパス情報を含むレスポンス

        Note:
            msgType=14: 動画ファイル
            channelType=10: グループチャット
        """
        url = f"{self.base_url}/p/oneapp/client/chat/issueResourcePath"
        headers = self._get_common_headers()
        headers.update(
            {
                "content-type": "application/json;charset=UTF-8",
                "priority": "u=1, i",
            }
        )

        if isinstance(file_data, bytes):
            file_data = base64.b64encode(file_data).decode("utf-8")

        data = {
            "serviceId": "works",
            "channelNo": channel_no,
            "filename": filename,
            "filesize": len(base64.b64decode(file_data)),
            "msgType": 14,
            "channelType": 10,
        }

        response = requests.post(
            url,
            headers=headers,
            cookies=self.cookies,
            json=data,
            timeout=30,
        )
        return response.json()

    def upload_file_options(self, resource_path: str) -> int:
        """ファイルアップロードのOPTIONSリクエスト.

        Args:
            resource_path (str): リソースパス

        Returns:
            int: レスポンスのステータスコード
        """
        url = f"{self.storage_url}{resource_path}"
        params = {
            "Servicekey": "oneapp",
            "writeMode": "overwrite",
            "isMakethumbnail": "true",
        }
        headers = {
            "Accept": "*/*",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Access-Control-Request-Headers": (
                "device-language,x-callerno,x-channelno,x-extras,"
                "x-ocn,x-resourcepath,x-serviceid,x-tid,x-type"
            ),
            "Access-Control-Request-Method": "POST",
            "Connection": "keep-alive",
            "Origin": "https://talk.worksmobile.com",
            "Referer": "https://talk.worksmobile.com/",
        }

        response = requests.options(
            url, headers=headers, params=params, timeout=30
        )
        return response.status_code

    def upload_file(
        self, resource_path: str, file_data: Union[bytes, str]
    ) -> Dict:
        """動画ファイルをアップロード.

        Args:
            resource_path (str): リソースパス
            file_data (Union[bytes, str]): ファイルのバイナリデータまたはBase64

        Returns:
            Dict: アップロード結果を含むレスポンス

        Note:
            code=416, message="Filesize must be greater than 0"の場合は
            拡張子が対応外のファイルである可能性があります。
        """
        uploader = VideoUploader(file_data)
        if uploader.file_size == 0:
            return {"code": -1}

        logger.info("File size: %d bytes", uploader.file_size)

        url = f"{self.storage_url}{resource_path}"
        params = {
            "Servicekey": "oneapp",
            "writeMode": "overwrite",
            "isMakethumbnail": "true",
        }

        boundary = "----WebKitFormBoundaryIDpMEPWWgRoczkxm"
        extras = {
            "filesize": uploader.file_size,
            "filename": os.path.basename(resource_path),
            "resourcepath": resource_path,
            "recordtime": uploader.duration,  # 動画の長さ（秒）
        }

        headers = self._get_common_headers()
        headers.update(
            {
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Device-Language": "ja_JP",
                "x-resourcepath": resource_path,
                "x-serviceid": "works",
                "x-type": "14",  # 動画用のタイプ
                "x-callerno": self.caller_no,
                "x-channelno": self.channel_no,
                "x-extras": json.dumps(extras),
                "x-ocn": "1",
                "x-tid": str(int(time.time() * 1000)),
            }
        )

        form = []
        form.append(f"--{boundary}")
        form.append(
            f"Content-Disposition: form-data; "
            f'name="file"; '
            f'filename="{os.path.basename(resource_path)}"'
        )
        form.append("Content-Type: video/mp4")
        form.append("")
        form.append(uploader.file_data)
        form.append(f"--{boundary}--")

        form_data = b"\r\n".join(
            [
                part.encode("utf-8") if isinstance(part, str) else part
                for part in form
            ]
        )

        headers["Content-Length"] = str(len(form_data))

        try:
            response = requests.post(
                url,
                headers=headers,
                params=params,
                cookies=self.cookies,
                data=form_data,
                timeout=30,
            )

            try:
                return response.json()
            except ValueError:
                logger.error("Response status: %d", response.status_code)
                logger.error("Response text: %s", response.text)
                return {"code": response.status_code}

        except requests.exceptions.RequestException as e:
            logger.error("Upload error: %s", str(e))
            return {"code": -1}


def main() -> None:
    """メイン処理."""
    channel_no = "307464837"
    caller_no = "110002509764123"
    api = WorksVideoAPI(channel_no=channel_no, caller_no=caller_no)

    # ファイルパスを修正
    file_path = os.path.join(os.path.dirname(__file__), "files", "video.mp4")

    # ファイルの存在確認
    if not os.path.exists(file_path):
        logger.error("File not found: %s", file_path)
        return

    with open(file_path, "rb") as f:
        file_data = f.read()

    # ファイルサイズの確認
    if len(file_data) == 0:
        logger.error("File is empty")
        return

    base64_data = base64.b64encode(file_data).decode("utf-8")
    resource_info = api.issue_resource_path(
        os.path.basename(file_path), base64_data, int(channel_no)
    )
    logger.info("Resource Info: %s", resource_info)

    if resource_info.get("code") != 200:
        logger.error("Failed to get resource path: %s", resource_info)
        return

    resource_path = resource_info["resourcePath"]

    status = api.upload_file_options(resource_path)
    logger.info("Options Status: %s", status)

    result = api.upload_file(resource_path, file_data)
    logger.info("Upload Result: %s", result)


if __name__ == "__main__":
    main()
