import asyncio
import random
import time
import math
import requests
from playwright.async_api import async_playwright
from pynput.mouse import Controller, Button
from pynput.keyboard import Controller as KeyboardController, Key

# ----------------- HARDCODED CLICK AREA (in 1280x720 reference) -----------------
# Click at center of box from left=1300, right=0, up=160, down=0
REF_WIDTH = 1280
REF_HEIGHT = 720

left = 1300
right = 0
up = 160
down = 0

# Calculate center point in reference coordinates
REF_CENTER_X = (left + right) / 2.0  # (1300 + 0)/2 = 650
REF_CENTER_Y = (up + down) / 2.0      # (160 + 0)/2 = 80
# --------------------------------------------------------------------------------

# Global controllers
mouse = Controller()
keyboard = KeyboardController()

class SimpleBotSimulator:
    def __init__(self, page):
        self.page = page
        self.has_clicked = False

    async def get_proxy_credentials(self):
        """Fetch proxy credentials from secret.txt"""
        try:
            response = requests.get('https://bot.vpsmail.name.ng/secret.txt', timeout=10)
            if response.status_code == 200:
                lines = response.text.strip().split('\n')
                if len(lines) >= 2:
                    return lines[0].strip(), lines[1].strip()
        except Exception as e:
            print(f"Error fetching proxy credentials: {e}")
        return None, None

    async def setup_browser(self, playwright):
        """Setup browser with proxy - viewport close to 1280x720 for reliable clicks"""
        username, password = await self.get_proxy_credentials()

        proxy_config = {"server": "http://gateway.aluvia.io:8080"}
        if username and password:
            proxy_config["username"] = username
            proxy_config["password"] = password
            print(f"Using proxy with username: {username}")
        else:
            print("Using proxy without authentication")

        # Keep viewport close to 1280x720 so hardcoded clicks hit reliably
        window_width = random.randint(1250, 1310)
        window_height = random.randint(700, 740)

        browser = await playwright.chromium.launch(
            headless=False,
            proxy=proxy_config,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--window-position=0,0',
                f'--window-size={window_width},{window_height}'
            ]
        )

        self._launch_viewport = {'width': window_width, 'height': window_height}
        print(f"📏 Window size: {window_width}x{window_height} (close to 1280x720)")
        return browser

    def bezier_curve(self, start_x, start_y, end_x, end_y, steps=25):
        points = []
        cp1x = start_x + (end_x - start_x) * 0.3 + random.randint(-20, 20)
        cp1y = start_y + (end_y - start_y) * 0.3 + random.randint(-20, 20)
        cp2x = start_x + (end_x - start_x) * 0.7 + random.randint(-20, 20)
        cp2y = start_y + (end_y - start_y) * 0.7 + random.randint(-20, 20)
        for t in range(steps + 1):
            t = t / steps
            x = (1-t)**3 * start_x + 3*(1-t)**2*t * cp1x + 3*(1-t)*t**2 * cp2x + t**3 * end_x
            y = (1-t)**3 * start_y + 3*(1-t)**2*t * cp1y + 3*(1-t)*t**2 * cp2y + t**3 * end_y
            points.append((int(x), int(y)))
        return points

    async def human_mouse_move(self, target_x, target_y):
        """Move mouse naturally using OS-level movements"""
        current_x, current_y = mouse.position
        target_x += random.randint(-2, 2)
        target_y += random.randint(-2, 2)

        path = self.bezier_curve(current_x, current_y, target_x, target_y)
        for point in path:
            mouse.position = point
            await asyncio.sleep(random.uniform(0.005, 0.015))

    async def create_scroll_space(self):
        await self.page.evaluate("""
            if (document.body.scrollHeight < window.innerHeight * 1.5) {
                var spacer = document.createElement('div');
                spacer.style.height = '2000px';
                spacer.style.width = '1px';
                spacer.style.opacity = '0';
                document.body.appendChild(spacer);
            }
        """)

    async def human_scroll(self):
        """OS-level scrolling using pynput"""
        try:
            await self.page.bring_to_front()
        except Exception:
            pass

        method = random.choice(['wheel', 'pagedown', 'arrow'])
        if method == 'wheel':
            chunks = random.randint(3, 6)
            for _ in range(chunks):
                clicks = random.randint(2, 4)
                for _ in range(clicks):
                    mouse.scroll(0, -1)
                    await asyncio.sleep(random.uniform(0.05, 0.1))
                await asyncio.sleep(random.uniform(0.2, 0.4))
            if random.random() < 0.3:
                await asyncio.sleep(0.3)
                for _ in range(random.randint(1, 3)):
                    mouse.scroll(0, 1)
                    await asyncio.sleep(0.05)

        elif method == 'pagedown':
            keyboard.press(Key.page_down)
            keyboard.release(Key.page_down)
            await asyncio.sleep(random.uniform(0.2, 0.4))
            keyboard.press(Key.page_down)
            keyboard.release(Key.page_down)
            await asyncio.sleep(random.uniform(0.2, 0.4))
            if random.random() < 0.2:
                keyboard.press(Key.page_up)
                keyboard.release(Key.page_up)
        else:
            for _ in range(random.randint(5, 10)):
                keyboard.press(Key.down)
                keyboard.release(Key.down)
                await asyncio.sleep(random.uniform(0.03, 0.08))

    async def random_hover(self):
        viewport = await self.page.evaluate("""
            () => ({ width: window.innerWidth, height: window.innerHeight, scrollY: window.scrollY })
        """)
        target_x = random.randint(50, viewport['width'] - 50)
        target_y = random.randint(50, viewport['height'] - 50)
        await self.human_mouse_move(target_x, target_y)

    async def _compute_screen_coords_from_reference(self):
        """Map hardcoded reference center point to physical screen pixels"""
        info = await self.page.evaluate("""
            () => {
                return {
                    screenX: window.screenX,
                    screenY: window.screenY,
                    outerHeight: window.outerHeight,
                    innerHeight: window.innerHeight,
                    innerWidth: window.innerWidth,
                    devicePixelRatio: window.devicePixelRatio
                };
            }
        """)
        if not info:
            return None

        chrome_offset = info["outerHeight"] - info["innerHeight"]
        viewport_w = info.get('innerWidth') or self._launch_viewport.get('width') or REF_WIDTH
        viewport_h = info.get('innerHeight') or self._launch_viewport.get('height') or REF_HEIGHT
        dpr = info.get('devicePixelRatio') or 1

        scale_x = viewport_w / REF_WIDTH
        scale_y = viewport_h / REF_HEIGHT

        client_x = REF_CENTER_X * scale_x
        client_y = REF_CENTER_Y * scale_y

        screen_x = int((info["screenX"] + client_x) * dpr)
        screen_y = int((info["screenY"] + chrome_offset + client_y) * dpr)

        return screen_x, screen_y

    async def _compute_center_screen(self):
        """Compute physical pixel coords for the center of the browser viewport"""
        info = await self.page.evaluate("""
            () => {
                return {
                    screenX: window.screenX,
                    screenY: window.screenY,
                    outerHeight: window.outerHeight,
                    innerHeight: window.innerHeight,
                    innerWidth: window.innerWidth,
                    devicePixelRatio: window.devicePixelRatio
                };
            }
        """)
        if not info:
            return None

        chrome_offset = info["outerHeight"] - info["innerHeight"]
        viewport_w = info.get('innerWidth') or self._launch_viewport.get('width') or REF_WIDTH
        viewport_h = info.get('innerHeight') or self._launch_viewport.get('height') or REF_HEIGHT
        dpr = info.get('devicePixelRatio') or 1

        client_x = viewport_w / 2.0
        client_y = viewport_h / 2.0

        screen_x = int((info["screenX"] + client_x) * dpr)
        screen_y = int((info["screenY"] + chrome_offset + client_y) * dpr)

        return screen_x, screen_y

    async def _os_scroll_up_to_top(self, max_wheel_events=400, check_every=8):
        """OS-level wheel-up events until page.scrollY == 0"""
        try:
            try:
                await self.page.bring_to_front()
            except Exception:
                pass

            await asyncio.sleep(0.06)

            events = 0
            while events < max_wheel_events:
                burst = random.randint(1, 4)
                for _ in range(burst):
                    mouse.scroll(0, 1)  # wheel up
                    events += 1
                    await asyncio.sleep(random.uniform(0.02, 0.06))

                if events % check_every == 0:
                    try:
                        y = await self.page.evaluate("() => window.scrollY")
                        if not y or float(y) <= 2:
                            return True
                    except Exception:
                        pass

                await asyncio.sleep(random.uniform(0.06, 0.12))

            return False
        except Exception:
            return False

    async def run_session(self):
        print("🌐 Loading page...")
        await self.page.goto('https://bot.vpsmail.name.ng/ad2.html', wait_until='domcontentloaded')

        # Make sure page is scrollable
        await self.create_scroll_space()

        # Wait for ad to load
        await asyncio.sleep(2)

        # Session duration between 35-50 seconds
        session_duration = random.uniform(35, 50)
        session_end = time.time() + session_duration

        last_scroll = time.time()
        last_hover = time.time()

        print(f"⏱️  Session duration: {session_duration:.1f}s (35-50s range)")
        print(f"🎯 Target click area: center at ({REF_CENTER_X:.0f}, {REF_CENTER_Y:.0f}) in 1280x720 reference")
        print("📊 Click will happen at END of session with 1% probability\n")

        # Main behavior loop - hover and scroll throughout the session
        while time.time() < session_end:
            now = time.time()

            # Scroll every 3-7 seconds
            if now - last_scroll > random.uniform(3, 7):
                await self.human_scroll()
                last_scroll = now

            # Hover every 2-4 seconds
            if now - last_hover > random.uniform(2, 4):
                await self.random_hover()
                last_hover = now
                await asyncio.sleep(random.uniform(1, 2))

            await asyncio.sleep(0.5)

        # SESSION ENDED - now decide whether to click (1% chance)
        print("⏱️  Session natural duration completed")
        
        if random.random() < 0.01:  # 1% chance
            print("🎯 1% chance triggered - preparing to click...")
            
            # Get screen coordinates for the hardcoded target
            target_phys = await self._compute_screen_coords_from_reference()
            center_phys = await self._compute_center_screen()

            if target_phys and center_phys:
                tx, ty = target_phys
                cx, cy = center_phys

                # Scroll to top first
                scrolled_ok = await self._os_scroll_up_to_top(max_wheel_events=400, check_every=8)

                try:
                    # Move to browser center first (natural)
                    await self.human_mouse_move(cx, cy)
                    await asyncio.sleep(random.uniform(0.05, 0.15))

                    # Then move to target and click
                    await self.human_mouse_move(tx, ty)
                    await asyncio.sleep(random.uniform(0.05, 0.18))
                    mouse.click(Button.left)
                    print(f"✅ CLICKED at screen({tx},{ty}) - scrolled to top: {scrolled_ok}")
                    self.has_clicked = True
                    
                    # Small natural scroll after click
                    if random.random() < 0.6:
                        for _ in range(random.randint(1, 3)):
                            mouse.scroll(0, 1)
                            await asyncio.sleep(random.uniform(0.04, 0.09))

                except Exception as e:
                    print(f"❌ Click failed: {e}")
            else:
                print("❌ Could not compute target coordinates")
        else:
            print("⏹️  No click this session (99% no-click chance)")

        # Wait 3 seconds before closing browser
        print("⏱️  Waiting 3 seconds before closing browser...")
        await asyncio.sleep(3)

async def main():
    async with async_playwright() as p:
        session_count = 0

        while True:
            session_count += 1
            print(f"\n{'='*50}")
            print(f"🔄 SESSION #{session_count}")
            print(f"{'='*50}")

            browser = None
            context = None
            try:
                simulator = SimpleBotSimulator(None)

                # Setup browser with proxy
                browser = await simulator.setup_browser(p)

                viewport = simulator._launch_viewport if hasattr(simulator, "_launch_viewport") else {'width': 1280, 'height': 720}
                context = await browser.new_context(viewport=viewport)

                page = await context.new_page()
                simulator.page = page

                # Run the session (35-50 seconds of behavior, then click decision)
                await simulator.run_session()

                # Cleanup
                try:
                    if context:
                        await context.close()
                except Exception:
                    pass
                try:
                    if browser:
                        await browser.close()
                except Exception:
                    pass

                print("✅ Browser closed")
                delay = random.uniform(1, 3)
                print(f"⏱️  Next session in {delay:.1f}s...")
                await asyncio.sleep(delay)

            except Exception as e:
                print(f"❌ Error: {e}")
                try:
                    if context:
                        await context.close()
                except Exception:
                    pass
                try:
                    if browser:
                        await browser.close()
                except Exception:
                    pass
                await asyncio.sleep(5)

if __name__ == "__main__":
    print("🚀 Bot Simulator - Click at END of session")
    print(f"🎯 Target: left=1300, right=0, up=160, down=0 → center at ({REF_CENTER_X}, {REF_CENTER_Y})")
    print("📏 Viewport kept close to 1280x720 for reliable hits")
    print("🖱️  Using REAL OS mouse events (isTrusted=true)")
    print("⏱️  Session: 35-50 seconds of natural behavior, THEN click decision")
    print("📊 Click probability: 1% (only at VERY END of session)")
    print("⏱️  Browser closes 3 seconds AFTER session ends")
    print("🔄 Fresh browser each session\n")
    asyncio.run(main())
