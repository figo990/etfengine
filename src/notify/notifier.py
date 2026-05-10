"""通知引擎：统一的消息推送管理"""

from __future__ import annotations

import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from loguru import logger


class BaseNotifier(ABC):
    """通知渠道基类"""

    @abstractmethod
    def send(self, title: str, content: str) -> bool:
        ...


class EmailNotifier(BaseNotifier):
    """邮件通知（SMTP）"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        receiver: str = "",
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.receiver = receiver or username

    def send(self, title: str, content: str) -> bool:
        if not self.smtp_host or not self.username:
            logger.warning("[Email] SMTP 未配置，跳过发送")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = title
        msg["From"] = self.username
        msg["To"] = self.receiver
        msg.attach(MIMEText(content, "html", "utf-8"))

        try:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=15) as srv:
                srv.login(self.username, self.password)
                srv.send_message(msg)
            logger.info(f"[Email] 发送成功: {title}")
            return True
        except Exception as e:
            logger.error(f"[Email] 发送失败: {e}")
            return False


class WeChatNotifier(BaseNotifier):
    """企业微信 Webhook 通知"""

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, title: str, content: str) -> bool:
        if not self.webhook_url:
            logger.warning("[WeChat] Webhook URL 未配置，跳过发送")
            return False

        payload = {
            "msgtype": "markdown",
            "markdown": {"content": f"### {title}\n{content}"},
        }

        try:
            resp = httpx.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("errcode") == 0:
                    logger.info(f"[WeChat] 发送成功: {title}")
                    return True
                logger.warning(f"[WeChat] API 返回错误: {data}")
                return False
            logger.warning(f"[WeChat] HTTP {resp.status_code}")
            return False
        except Exception as e:
            logger.error(f"[WeChat] 发送失败: {e}")
            return False


class NotifyManager:
    """通知管理器：管理多渠道推送"""

    def __init__(self) -> None:
        self._channels: list[BaseNotifier] = []

    def add_channel(self, notifier: BaseNotifier) -> None:
        self._channels.append(notifier)

    def broadcast(self, title: str, content: str) -> None:
        """向所有渠道广播消息"""
        for channel in self._channels:
            try:
                channel.send(title, content)
            except Exception as e:
                logger.error(f"通知发送失败 ({type(channel).__name__}): {e}")
