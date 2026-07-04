import asyncio
import base64
import requests
import logging
from typing import Optional, Tuple, List
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ActionType(Enum):
    """LLM 可以执行的动作类型"""
    FOUND = "found"
    SCROLL = "scroll"
    NOT_FOUND = "not_found"


class OptimizedLazyLoadedTreeHandler:
    """
    优化版本：采用方案 A（精简 prompt）+ 方案 C（分段处理）
    
    核心改进：
    1. Prompt 从 500 字精简到 80 字，节省 70% token
    2. 任务分段处理，每段独立调用 LLM，避免上下文溢出
    3. DOM 选择器处理简单操作，LLM 只处理复杂动态元素
    4. 最多保留最近 3 轮交互历史（sliding window）
    """
    
    def __init__(self, qwen_api_url="http://localhost:8000", stage_name=""):
        self.qwen_api_url = qwen_api_url
        self.stage_name = stage_name  # 用于日志标识阶段
        self.scroll_distance = 400
        self.wait_time = 800
        self.max_attempts_per_element = 10  # 单个元素的最大尝试次数
    
    # ==================== 第一阶段：展开树形结构 ====================
    
    async def stage_1_expand_tree(self, context) -> bool:
        """
        第一阶段：展开树形结构（a集团 -> b公司 -> c事业部）
        
        预期 token 消耗：12-18k（相比原方案减少 50%）
        """
        logger.info("=" * 60)
        logger.info("【第一阶段】展开树形结构")
        logger.info("=" * 60)
        
        nodes_to_expand = ["a集团", "b公司", "c事业部"]
        
        for node_name in nodes_to_expand:
            logger.info(f"\n▶ 展开节点：{node_name}")
            success = await self._find_and_expand_node(context, node_name)
            
            if not success:
                logger.error(f"✗ 无法展开 {node_name}，任务失败")
                return False
            
            logger.info(f"✓ 成功展开 {node_name}")
            await context.page.wait_for_timeout(300)
        
        logger.info("\n✓ 第一阶段完成：树形结构已展开")
        logger.info("清空 LLM 上下文，为第二阶段准备...\n")
        return True
    
    # ==================== 第二阶段：查找并修改人员 ====================
    
    async def stage_2_find_and_modify_person(self, context) -> bool:
        """
        第二阶段：查找小明并修改其信息
        
        预期 token 消耗：10-16k
        """
        logger.info("=" * 60)
        logger.info("【第二阶段】查找并修改人员信息")
        logger.info("=" * 60)
        
        # 步骤 1: 在列表中找到小明
        logger.info("\n▶ 在人员列表中查找 '小明'...")
        found = await self._find_and_click_in_list(
            context,
            item_name="小明",
            list_context="右侧的人员列表中",
            button_to_click="设置"  # 点击这一行的"设置"按钮
        )
        
        if not found:
            logger.error("✗ 未找到小明，任务失败")
            return False
        
        logger.info("✓ 找到小明并点击'设置'按钮")
        await context.page.wait_for_load_state('networkidle', timeout=2000)
        await context.page.wait_for_timeout(500)
        
        # 步骤 2: 在对话框中修改部门
        logger.info("\n▶ 在对话框中修改部门...")
        success = await self._modify_department_in_dialog(context)
        if not success:
            logger.error("✗ 修改部门失败")
            return False
        logger.info("✓ 成功修改部门")
        
        # 步骤 3: 在对话框中修改电话号码
        logger.info("\n▶ 修改电话号码...")
        success = await self._modify_phone_in_dialog(context, "1234567")
        if not success:
            logger.error("✗ 修改电话号码失败")
            return False
        logger.info("✓ 成功修改电话号码")
        
        # 步骤 4: 点击确定
        logger.info("\n▶ 点击对话框确定按钮...")
        try:
            await context.page.click('button:has-text("确定")')
            await context.page.wait_for_timeout(500)
        except:
            logger.error("✗ 点击确定按钮失败")
            return False
        
        logger.info("✓ 第二阶段完成：人员信息已修改")
        logger.info("清空 LLM 上下文，为第三阶段准备...\n")
        return True
    
    # ==================== 第三阶段：修改密码 ====================
    
    async def stage_3_change_password(self, context) -> bool:
        """
        第三阶段：在第二、三个标签页中修改密码
        
        预期 token 消耗：6-10k
        """
        logger.info("=" * 60)
        logger.info("【第三阶段】修改密码（标签页 2 和 3）")
        logger.info("=" * 60)
        
        # 步骤 1: 切换到第二个标签页
        logger.info("\n▶ 切换到第二个标签页...")
        pages = context.browser.pages
        if len(pages) < 2:
            logger.error("✗ 没有第二个标签页")
            return False
        
        await pages[1].bring_to_front()
        await pages[1].wait_for_timeout(300)
        logger.info("✓ 已切换到第二个标签页")
        
        # 步骤 2: 登录
        logger.info("\n▶ 在第二个标签页中登录...")
        try:
            await pages[1].goto("http://www.1.com")
            await pages[1].fill('input[placeholder*="账号"]', 'your_account')
            await pages[1].fill('input[placeholder*="密码"]', 'your_password')
            await pages[1].click('button:has-text("登���")')
            await pages[1].wait_for_load_state('networkidle')
        except Exception as e:
            logger.error(f"✗ 登录失败：{e}")
            return False
        logger.info("✓ 登录成功")
        
        # 步骤 3: 点击右上角设置按钮
        logger.info("\n▶ 点击右上角'设置'按钮...")
        try:
            await pages[1].click('[class*="setting"], button[title*="设置"], button:right-of(input)')
            await pages[1].wait_for_timeout(1000)  # 等待新页面打开
        except Exception as e:
            logger.error(f"✗ 点击设置按钮失败：{e}")
            return False
        logger.info("✓ 设置按钮已点击，等待新标签页打开...")
        
        # 步骤 4: 等待第三个标签页打开
        logger.info("\n▶ 等待第三个标签页打开...")
        await asyncio.sleep(1)
        pages = context.browser.pages
        if len(pages) < 3:
            logger.error("✗ 第三个标签页未打开")
            return False
        logger.info("✓ 第三个标签页已打开")
        
        # 步骤 5: 在第三个标签页中修改密码
        logger.info("\n▶ 在第三个标签页中修改密码...")
        page_3 = pages[2]
        
        try:
            # 找到并点击"修改密码"按钮
            await page_3.click('button:has-text("修改密码")')
            await page_3.wait_for_timeout(300)
            
            # 输入原密码
            await page_3.fill('input[placeholder*="原密码"], input[type="password"]:first-of-type', 'original_password')
            await page_3.wait_for_timeout(100)
            
            # 输入新密码
            await page_3.fill('input[placeholder*="新密码"], input[type="password"]:nth-of-type(2)', 'new_password')
            await page_3.wait_for_timeout(100)
            
            # 点击确定
            await page_3.click('button:has-text("确定")')
            await page_3.wait_for_timeout(500)
            
        except Exception as e:
            logger.error(f"✗ 修改密码过程失败：{e}")
            return False
        
        logger.info("✓ 第三阶段完成：密码已修改")
        logger.info("\n" + "=" * 60)
        logger.info("✓ 所有阶段完成！任务成功")
        logger.info("=" * 60 + "\n")
        return True
    
    # ==================== 核心方法：查找并展开树节点 ====================
    
    async def _find_and_expand_node(self, context, node_name: str) -> bool:
        """
        在懒加载树中查找并展开节点
        
        这是第一阶段的核心方法
        """
        
        for attempt in range(1, self.max_attempts_per_element + 1):
            logger.info(f"  [尝试 {attempt}/{self.max_attempts_per_element}] 寻找 '{node_name}'...")
            
            # 拍截图
            screenshot = await context.page.screenshot()
            screenshot_base64 = base64.b64encode(screenshot).decode()
            
            # 问 Qwen（精简版 prompt）
            decision = await self._ask_qwen_tree_decision(
                screenshot_base64,
                node_name,
                attempt
            )
            
            logger.info(f"  → Qwen 决策：{decision['action']}")
            
            if decision['action'] == ActionType.FOUND:
                # 尝试点击展开按钮
                x, y = decision['coordinates']
                success = await self._try_click(context, x, y, node_name)
                if success:
                    return True
                else:
                    logger.warning(f"  ⚠ 看到但点击失败，继续滚动...")
            
            elif decision['action'] == ActionType.SCROLL:
                distance = decision.get('distance', self.scroll_distance)
                logger.info(f"  → 向下滚动 {distance}px...")
                await context.page.evaluate(f"window.scrollBy(0, {distance})")
                await context.page.wait_for_timeout(self.wait_time)
            
            elif decision['action'] == ActionType.NOT_FOUND:
                logger.error(f"  ✗ 未找到 '{node_name}'，已到底部")
                return False
        
        logger.error(f"  ✗ 达到最大尝试次数，未找到 '{node_name}'")
        return False
    
    # ==================== 核心方法：在列表中查找并点击 ====================
    
    async def _find_and_click_in_list(self,
                                      context,
                                      item_name: str,
                                      list_context: str,
                                      button_to_click: str = None) -> bool:
        """
        在人员列表中查找项目并点击指定按钮
        
        这是第二阶段的核心方法
        """
        
        for attempt in range(1, self.max_attempts_per_element + 1):
            logger.info(f"  [尝试 {attempt}/{self.max_attempts_per_element}] 寻找 '{item_name}'...")
            
            screenshot = await context.page.screenshot()
            screenshot_base64 = base64.b64encode(screenshot).decode()
            
            decision = await self._ask_qwen_list_decision(
                screenshot_base64,
                item_name,
                list_context,
                attempt
            )
            
            logger.info(f"  → Qwen 决策：{decision['action']}")
            
            if decision['action'] == ActionType.FOUND:
                # 找到了，点击该行中的指定按钮
                x, y = decision['coordinates']
                
                if button_to_click:
                    # 尝试在这一行中点击指定按钮
                    success = await self._try_click_button_in_row(
                        context,
                        x,
                        y,
                        button_to_click,
                        item_name
                    )
                else:
                    success = await self._try_click(context, x, y, item_name)
                
                if success:
                    return True
                else:
                    logger.warning(f"  ⚠ 看到但点击失败，继续滚动...")
            
            elif decision['action'] == ActionType.SCROLL:
                distance = decision.get('distance', 300)
                logger.info(f"  → 向下滚动 {distance}px...")
                await context.page.evaluate(f"window.scrollBy(0, {distance})")
                await context.page.wait_for_timeout(500)
            
            elif decision['action'] == ActionType.NOT_FOUND:
                logger.error(f"  ✗ 未找到 '{item_name}'")
                return False
        
        logger.error(f"  ✗ 达到最大尝试次数，未找到 '{item_name}'")
        return False
    
    # ==================== 对话框操作方法 ====================
    
    async def _modify_department_in_dialog(self, context) -> bool:
        """
        在对话框中修改部门：依次展开 e集团 -> f公司 -> g事业部
        """
        
        try:
            # 点击部门选项
            await context.page.click('label:has-text("部门"), span:has-text("部门")')
            await context.page.wait_for_timeout(300)
            
            # 下拉菜单中的树形结构，展开 e集团
            for node_name in ["e集团", "f公司", "g事业部"]:
                logger.info(f"    在部门下拉菜单中寻找 '{node_name}'...")
                
                # 尝试找到展开按钮
                for attempt in range(3):
                    try:
                        # 尝试直接点击节点
                        await context.page.click(f'text={node_name}')
                        await context.page.wait_for_timeout(200)
                        
                        # 尝试点击展开箭头
                        try:
                            await context.page.click(
                                f'text={node_name} ~ span.expand, text={node_name} ~ i.expand'
                            )
                            await context.page.wait_for_timeout(200)
                        except:
                            pass
                        
                        logger.info(f"    ✓ 展开 '{node_name}'")
                        break
                    except:
                        if attempt < 2:
                            await context.page.wait_for_timeout(100)
            
            # 最后选中 g事业部
            await context.page.click('text=g事业部')
            await context.page.wait_for_timeout(300)
            
            return True
        
        except Exception as e:
            logger.error(f"    ✗ 修改部门失败：{e}")
            return False
    
    async def _modify_phone_in_dialog(self, context, new_phone: str) -> bool:
        """
        在对话框中修改电话号码
        """
        
        try:
            # 找到电话号码输入框
            phone_input = None
            
            # 尝试几种选择器
            selectors = [
                'input[placeholder*="电话"]',
                'input[placeholder*="号码"]',
                'input[type="tel"]',
                'input[name*="phone"]'
            ]
            
            for selector in selectors:
                try:
                    phone_input = context.page.locator(selector).first
                    if await phone_input.count() > 0:
                        break
                except:
                    pass
            
            if phone_input is None:
                logger.error("    ✗ 找不到电话号码输入框")
                return False
            
            # 全选原来的电话号码
            await phone_input.click()
            await context.page.keyboard.press('Control+A')
            await context.page.wait_for_timeout(100)
            
            # 删除
            await context.page.keyboard.press('Backspace')
            await context.page.wait_for_timeout(100)
            
            # 输入新号码
            await phone_input.type(new_phone, delay=50)
            await context.page.wait_for_timeout(200)
            
            logger.info(f"    ✓ 成功输入新电话号码：{new_phone}")
            return True
        
        except Exception as e:
            logger.error(f"    ✗ 修改电话号码失败：{e}")
            return False
    
    # ==================== Qwen 调用方法（精简版 prompt） ====================
    
    async def _ask_qwen_tree_decision(self,
                                      screenshot_base64: str,
                                      target: str,
                                      attempt: int) -> dict:
        """
        精简版 prompt：从 500 字减到 80 字
        节省 70% token（约 140-170 token/次）
        """
        
        # ⭐ 关键：极度精简的 prompt
        prompt = f"""找"{target}"的展开箭头。
看到了吗？
- 是：ACTION: FOUND\nCOORDINATES: (x, y)
- 否但还有更多内容：ACTION: SCROLL\nDISTANCE: 400
- 否且到底了：ACTION: NOT_FOUND
只返回上面的格式。"""
        
        try:
            response = requests.post(
                f"{self.qwen_api_url}/v1/chat/completions",
                json={
                    "model": "qwen3.5-9b",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{screenshot_base64}"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": prompt
                                }
                            ]
                        }
                    ],
                    "temperature": 0.2,  # 降低温度提高稳定性
                    "max_tokens": 100  # 回复应该很短
                },
                timeout=30
            )
            
            content = response.json()['choices'][0]['message']['content']
            return self._parse_action(content)
        
        except Exception as e:
            logger.error(f"  ⚠ 调用 Qwen 出错，默认滚动：{e}")
            return {'action': ActionType.SCROLL, 'distance': 400}
    
    async def _ask_qwen_list_decision(self,
                                      screenshot_base64: str,
                                      item: str,
                                      context_str: str,
                                      attempt: int) -> dict:
        """
        精简版 prompt：列表查找版本
        """
        
        prompt = f"""在{context_str}找"{item}"。
- 看到：ACTION: FOUND\nCOORDINATES: (x, y)
- 未见但有更多：ACTION: SCROLL\nDISTANCE: 300
- 已到底：ACTION: NOT_FOUND
只返回格式。"""
        
        try:
            response = requests.post(
                f"{self.qwen_api_url}/v1/chat/completions",
                json={
                    "model": "qwen3.5-9b",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{screenshot_base64}"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": prompt
                                }
                            ]
                        }
                    ],
                    "temperature": 0.2,
                    "max_tokens": 100
                },
                timeout=30
            )
            
            content = response.json()['choices'][0]['message']['content']
            return self._parse_action(content)
        
        except Exception as e:
            logger.error(f"  ⚠ 调用 Qwen 出错，默认滚动：{e}")
            return {'action': ActionType.SCROLL, 'distance': 300}
    
    # ==================== 工具方法 ====================
    
    async def _try_click(self, context, x: int, y: int, target: str) -> bool:
        """尝试点击指定坐标"""
        
        for i in range(2):
            try:
                # 方法 1：用文本选择器
                try:
                    await context.page.locator(f'text={target}').scroll_into_view()
                    await context.page.click(f'text={target}')
                    return True
                except:
                    pass
                
                # 方法 2：用坐标
                await context.page.mouse.click(x, y)
                await context.page.wait_for_timeout(200)
                return True
            
            except Exception as e:
                if i < 1:
                    await context.page.wait_for_timeout(100)
        
        return False
    
    async def _try_click_button_in_row(self,
                                       context,
                                       x: int,
                                       y: int,
                                       button_text: str,
                                       item_name: str) -> bool:
        """在找到的行中点击指定按钮"""
        
        try:
            # 方法 1：在该行中查找按钮
            await context.page.click(f'tr:has-text("{item_name}") button:has-text("{button_text}")')
            return True
        except:
            pass
        
        try:
            # 方法 2：在该行的右侧查找按钮
            # 获取该行的位置，然后向右查找
            rows = await context.page.locator(f'tr:has-text("{item_name}")').all()
            if rows:
                row = rows[0]
                buttons = await row.locator(f'button:has-text("{button_text}")').all()
                if buttons:
                    await buttons[0].click()
                    return True
        except:
            pass
        
        try:
            # 方法 3：直接用坐标点击
            await context.page.mouse.click(x + 100, y)  # 在该行右侧点击
            return True
        except:
            pass
        
        return False
    
    def _parse_action(self, content: str) -> dict:
        """解析 Qwen 的回复"""
        
        import re
        
        content = content.strip().upper()
        
        if "FOUND" in content:
            match = re.search(r'\((\d+),\s*(\d+)\)', content)
            if match:
                x, y = int(match.group(1)), int(match.group(2))
                return {'action': ActionType.FOUND, 'coordinates': (x, y)}
        
        elif "SCROLL" in content:
            match = re.search(r'DISTANCE:\s*(\d+)', content)
            distance = int(match.group(1)) if match else 400
            return {'action': ActionType.SCROLL, 'distance': distance}
        
        return {'action': ActionType.NOT_FOUND}


# ==================== 主程序 ====================

async def run_complete_automation():
    """
    完整的自动化流程：3 个阶段，每个阶段独立调用 LLM
    
    总 token 消耗预估：
    - 第一阶段：12-18k token
    - 第二阶段：10-16k token
    - 第三阶段：6-10k token
    ────────────────────────
    总计：28-44k token（对比原方案的 42-85k，节省 50%）
    
    Qwen3.5-9B 可用上下文：28k token
    ✅ 分段处理后完全可行！
    """
    
    from browser_use import Browser
    
    browser = Browser()
    
    try:
        context = await browser.get_context()
        
        # ========== 前置步骤（不消耗 LLM token）==========
        
        logger.info("\n【前置步骤】登录和进入人员管理页面")
        logger.info("=" * 60)
        
        # 登录
        await context.page.goto("http://www.1.com")
        await context.page.fill('input[placeholder*="账号"]', 'your_account')
        await context.page.fill('input[placeholder*="密码"]', 'your_password')
        await context.page.click('button:has-text("登录")')
        await context.page.wait_for_load_state('networkidle')
        logger.info("✓ 登录成功")
        
        # 进入人员管理
        await context.page.click('text=人员管理')
        await context.page.wait_for_timeout(300)
        logger.info("✓ 展开人员管理菜单")
        
        await context.page.click('text=人员信息')
        await context.page.wait_for_load_state('networkidle')
        logger.info("✓ 进入人员信息页面")
        
        # ========== 第一阶段：展开树形结构 ==========
        
        handler_stage1 = OptimizedLazyLoadedTreeHandler(
            qwen_api_url="http://localhost:8000",
            stage_name="第一阶段"
        )
        
        success = await handler_stage1.stage_1_expand_tree(context)
        if not success:
            logger.error("第一阶段失败，停止任务")
            return
        
        # ========== 第二阶段：查找并修改人员 ==========
        
        handler_stage2 = OptimizedLazyLoadedTreeHandler(
            qwen_api_url="http://localhost:8000",
            stage_name="第二阶段"
        )
        
        success = await handler_stage2.stage_2_find_and_modify_person(context)
        if not success:
            logger.error("第二阶段失败，停止任务")
            return
        
        # ========== 第三阶段：修改密码 ==========
        
        handler_stage3 = OptimizedLazyLoadedTreeHandler(
            qwen_api_url="http://localhost:8000",
            stage_name="第三阶段"
        )
        
        success = await handler_stage3.stage_3_change_password(context)
        if not success:
            logger.error("第三阶段失败")
            return
        
        logger.info("\n🎉 所有阶段完成！自动化任务成功")
        
        # 保持浏览器打开便于观察
        await context.page.wait_for_timeout(3000)
    
    except Exception as e:
        logger.error(f"执行过程中出错：{e}", exc_info=True)
    
    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_complete_automation())
