from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from datetime import datetime
from pathlib import Path
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
import json
import random
import astrbot.api.message_components as Comp
import re

from .phi_save import save_svg
from .b30 import convert_svg_to_png


@register("phiplugin", "ALiNorn", "Phigros B30查询", "1.0.0")
class PhiPlugin(Star):

    def __init__(self, context: Context, config: dict) -> None:
        super().__init__(context, config)

        # 路径
        self.data_path = Path(get_astrbot_data_path()) / "plugin_data" / self.name
        self.data_path.mkdir(parents=True, exist_ok=True)

        self.json_file = self.data_path / "phi_bindings.json"
        self.lock_file = self.json_file.with_suffix(".lock")

        # 加载配置 —— 注意这里是 config，不是 self.config
        self.openapi_token = config.get("openapi_token", "")

        # 加载数据
        self.data = self._load_json()

        if not self.openapi_token:
            logger.warning("phiplugin: 未配置 openapi_token，API 请求将失败！")

    # ================= 工具方法 =================

    def _load_json(self) -> dict:
        """安全加载 JSON"""
        if not self.json_file.exists():
            return {"version": 1, "bindings": {}}

        try:
            with open(self.json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("version") != 1:
                    return self._migrate(data)
                return data
        except (json.JSONDecodeError, Exception):
            logger.warning("phi_bindings.json 损坏，已重置")
            return {"version": 1, "bindings": {}}

    def _migrate(self, old: dict) -> dict:
        """旧数据迁移预留"""
        return {
            "version": 1,
            "bindings": old.get("bindings", {})
        }

    def _save_json(self):
        """原子写 + 锁"""
        self.lock_file.touch()
        try:
            tmp = self.json_file.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            tmp.replace(self.json_file)
        finally:
            self.lock_file.unlink(missing_ok=True)

    def _now(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ================= 业务方法 =================

    def _get_binding(self, user_id: str) -> dict | None:
        """获取用户绑定信息"""
        return self.data["bindings"].get(user_id)

    def _set_binding(self, user_id: str, user_name: str, session_token: str):
        """设置绑定"""
        self.data["bindings"][user_id] = {
            "user_name": user_name,
            "session_token": session_token,
            "bind_time": self._now(),
            "last_update": self._now()
        }
        self._save_json()

    def _remove_binding(self, user_id: str):
        """解绑"""
        self.data["bindings"].pop(user_id, None)
        self._save_json()

    def _is_bound(self, user_id: str) -> bool:
        return user_id in self.data["bindings"]

    def _update_binding(self, user_id: str, **kwargs):
        """更新绑定信息"""
        if user_id in self.data["bindings"]:
            self.data["bindings"][user_id].update(kwargs)
            self._save_json()

    # ================= 指令 =================

    @filter.command("phi_bind")
    async def phi_bind(self, event: AstrMessageEvent):
        """绑定 Phi 账号"""
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        parts = event.message_str.strip().split()

        if len(parts) < 2:
            yield event.plain_result("用法: /phi_bind <session_token>")
            return

        session_token = parts[1]
        self._set_binding(user_id, user_name, session_token)

        yield event.plain_result(f"# 绑定成功! {user_name}")

    @filter.command("phi_unbind")
    async def phi_unbind(self, event: AstrMessageEvent):
        """解绑 Phi 账号"""
        user_id = event.get_sender_id()

        if not self._is_bound(user_id):
            yield event.plain_result("你还没有绑定 Phi 账号")
            return

        self._remove_binding(user_id)
        yield event.plain_result("已解绑 Phi 账号")

    @filter.command("phi_status")
    async def phi_status(self, event: AstrMessageEvent):
        """查看绑定状态"""
        user_id = event.get_sender_id()
        binding = self._get_binding(user_id)

        if not binding:
            yield event.plain_result("未绑定 Phi 账号")
            return

        yield event.plain_result(
            f"绑定信息:\n"
            f"用户: {binding['user_name']}\n"
            f"Session Token: {binding['session_token']}\n"
            f"绑定时间: {binding['bind_time']}\n"
            f"上次更新时间: {binding['last_update']}"
        )

    @filter.command("phi_update",alias=["pu","pupdate"])
    async def phi_update(self, event: AstrMessageEvent):
        """更新 Phi 数据"""
        user_id = event.get_sender_id()
        binding = self._get_binding(user_id)

        if not binding:
            yield event.plain_result("你还没有绑定 Phi 账号，请先使用 /phi_bind <session_token> 进行绑定")
            return

        session_token = binding["session_token"]
        svg_output_path = Path(self.data_path / session_token / "save.svg")
        svg_output_path.parent.mkdir(parents=True, exist_ok=True)

        # 调用 save_svg 函数
        try:
            save_svg(session_token, str(svg_output_path), self.openapi_token)
            self._update_binding(user_id, last_update=self._now())
            yield event.plain_result("Phi 数据已更新并保存")
        except Exception as e:
            yield event.plain_result(f"更新 Phi 数据时出错: {str(e)}")

    @filter.command("phi_b30",alias=["pb30","rks","pgr"])
    async def phi_b30(self, event: AstrMessageEvent):
        """将 save.svg 转换为 output.png"""
        user_id = event.get_sender_id()
        binding = self._get_binding(user_id)

        if not binding:
            yield event.plain_result("你还没有绑定 Phi 账号，请先使用 /phi_bind <session_token> 进行绑定")
            return

        session_token = binding["session_token"]
        last_time = binding["last_update"]

        svg_path = Path(self.data_path / session_token / "save.svg")
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        png_path = Path(self.data_path / session_token / "output.png")
        png_path.parent.mkdir(parents=True, exist_ok=True)

        # 检查 SVG 文件是否存在
        if not svg_path.exists():
            yield event.plain_result("存档文件不存在，请先使用 /phi_update 更新数据")
            return

        # 调用 convert_svg_to_png 函数
        try:
            await convert_svg_to_png(str(svg_path), str(png_path))
            yield event.plain_result("上次更新时间: " + last_time)
            yield event.image_result(str(png_path))
        except Exception as e:
            yield event.plain_result(f"转换存档为 PNG 时出错: {str(e)}")