import asyncio
import random
import time
import math
import requests
from playwright.async_api import async_playwright
from pynput.mouse import Controller, Button
from pynput.keyboard import Controller as KeyboardController, Key

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
        """Setup browser with proxy"""
        username, password = await self.get_proxy_credentials()
        
        proxy_config = {"server": "gateway.aluvia.io:8080"}
        if username and password:
            proxy_config["username"] = username
            proxy_config["password"] = password
            print(f"Using proxy with username: {username}")
        else:
            print("Using proxy without authentication")
            
        browser = await playwright.chromium.launch(
            headless=False,
            proxy=proxy_config,
            args=['--disable-blink-features=AutomationControlled']
        )
        return browser

    def bezier_curve(self, start_x, start_y, end_x, end_y, steps=25):
        """Simple bezier curve for natural movement"""
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
        """Make page scrollable if it isn't already"""
        await self.page.evaluate("""
            if (document.body.scrollHeight < window.innerHeight * 1.5) {
                var spacer = document.createElement('div');
                spacer.style.height = '2000px';
                spacer.style.width = '1px';
                spacer.style.opacity = '0';
                document.body.appendChild(spacer);
                console.log('Added scroll spacer');
            }
        """)

    async def human_scroll(self):
        """OS-level scrolling using pynput - REAL scroll events"""
        
        # Choose scroll method
        method = random.choice(['wheel', 'pagedown', 'arrow'])
        
        if method == 'wheel':
            # Mouse wheel scrolling (most natural)
            chunks = random.randint(3, 6)
            for _ in range(chunks):
                clicks = random.randint(2, 4)
                for _ in range(clicks):
                    mouse.scroll(0, -1)  # REAL scroll event!
                    await asyncio.sleep(random.uniform(0.05, 0.1))
                await asyncio.sleep(random.uniform(0.2, 0.4))
                
            # Sometimes scroll back up
            if random.random() < 0.3:
                await asyncio.sleep(0.3)
                for _ in range(random.randint(1, 3)):
                    mouse.scroll(0, 1)  # Scroll up
                    await asyncio.sleep(0.05)
                    
        elif method == 'pagedown':
            # Page Down key - also generates scroll events
            keyboard.press(Key.page_down)
            keyboard.release(Key.page_down)
            await asyncio.sleep(random.uniform(0.2, 0.4))
            keyboard.press(Key.page_down)
            keyboard.release(Key.page_down)
            await asyncio.sleep(random.uniform(0.2, 0.4))
            
            # Maybe page up
            if random.random() < 0.2:
                keyboard.press(Key.page_up)
                keyboard.release(Key.page_up)
                
        else:  # arrow keys
            # Arrow down - smaller scrolls
            for _ in range(random.randint(5, 10)):
                keyboard.press(Key.down)
                keyboard.release(Key.down)
                await asyncio.sleep(random.uniform(0.03, 0.08))

    async def find_clickable_elements(self):
        """Find anything clickable on the page"""
        elements = await self.page.evaluate("""
            () => {
                const clickables = [];
                
                // Surfe ad container
                const surfeAd = document.querySelector('.surfe-be');
                if (surfeAd) {
                    const rect = surfeAd.getBoundingClientRect();
                    if (rect.width > 10 && rect.height > 10) {
                        clickables.push({
                            type: 'surfe-ad',
                            x: rect.left + rect.width/2,
                            y: rect.top + rect.height/2
                        });
                    }
                }
                
                // Iframes
                document.querySelectorAll('iframe').forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 50 && rect.height > 50) {
                        clickables.push({
                            type: 'iframe',
                            x: rect.left + rect.width/2,
                            y: rect.top + rect.height/2
                        });
                    }
                });
                
                // Links, buttons, clickable elements
                document.querySelectorAll('a, button, [onclick], .clickable').forEach(el => {
                    if (el.offsetParent !== null) {
                        const rect = el.getBoundingClientRect();
                        clickables.push({
                            type: el.tagName.toLowerCase(),
                            x: rect.left + rect.width/2,
                            y: rect.top + rect.height/2
                        });
                    }
                });
                
                return clickables;
            }
        """)
        return elements

    async def random_hover(self):
        """Move mouse randomly around the page"""
        viewport = await self.page.evaluate("""
            () => ({
                width: window.innerWidth,
                height: window.innerHeight,
                scrollY: window.scrollY
            })
        """)
        
        target_x = random.randint(50, viewport['width'] - 50)
        target_y = random.randint(50, viewport['height'] - 50)
        
        await self.human_mouse_move(target_x, target_y)

    async def run_session(self):
        """Main session loop"""
        print("🌐 Loading page...")
        await self.page.goto('https://bot.vpsmail.name.ng/ad2.html', wait_until='domcontentloaded')
        
        # Make sure page is scrollable
        await self.create_scroll_space()
        
        # Wait for ad to load
        await asyncio.sleep(2)
        
        # Session duration between 20-30 seconds
        session_duration = random.uniform(20, 30)
        session_end = time.time() + session_duration
        
        # Track when we can first click (after 15-20 seconds)
        min_click_time = time.time() + random.uniform(15, 20)
        
        last_scroll = time.time()
        last_hover = time.time()
        
        print(f"⏱️  Session duration: {session_duration:.1f}s")
        print(f"🖱️  First click possible after: {(min_click_time - time.time()):.1f}s")
        print(f"📊 Click probability: 39% (if clickable elements exist)\n")
        
        while time.time() < session_end:
            now = time.time()
            
            # Only consider clicking after minimum time has passed
            if now >= min_click_time and not self.has_clicked:
                # Find clickable elements
                clickables = await self.find_clickable_elements()
                
                # 39% chance to click if anything exists
                if clickables and random.random() < 0.39:
                    target = random.choice(clickables)
                    
                    # Get current scroll position
                    scroll_y = await self.page.evaluate("window.scrollY")
                    
                    # If target is far down, scroll there first
                    if abs(target['y'] - scroll_y) > 300:
                        scroll_needed = (target['y'] - scroll_y) // 100
                        for _ in range(abs(scroll_needed)):
                            if scroll_needed > 0:
                                mouse.scroll(0, -1)
                            else:
                                mouse.scroll(0, 1)
                            await asyncio.sleep(0.05)
                        await asyncio.sleep(0.3)
                    
                    # Click it
                    await self.human_mouse_move(target['x'], target['y'])
                    await asyncio.sleep(random.uniform(0.1, 0.2))
                    mouse.click(Button.left)
                    print(f"✅ CLICKED: {target['type']} at {now - (session_end - session_duration):.1f}s")
                    self.has_clicked = True
                    await asyncio.sleep(random.uniform(1, 2))
            
            # Scroll every 3-7 seconds using REAL OS scroll
            if now - last_scroll > random.uniform(3, 7):
                await self.human_scroll()
                last_scroll = now
            
            # Hover every 2-4 seconds
            if now - last_hover > random.uniform(2, 4):
                await self.random_hover()
                last_hover = now
                await asyncio.sleep(random.uniform(1, 2))
            
            await asyncio.sleep(0.5)
        
        # Session summary
        if self.has_clicked:
            print(f"✅ Session ended - click performed")
        else:
            print(f"⏹️  Session ended - no click (39% chance didn't trigger)")

async def main():
    async with async_playwright() as p:
        session_count = 0
        
        while True:
            session_count += 1
            print(f"\n{'='*50}")
            print(f"🔄 SESSION #{session_count} STARTING")
            print(f"{'='*50}")
            
            try:
                simulator = SimpleBotSimulator(None)
                
                # Setup browser with proxy
                browser = await simulator.setup_browser(p)
                
                # Create context
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 720}
                )
                
                page = await context.new_page()
                simulator.page = page
                
                # Run the session
                await simulator.run_session()
                
                # Cleanup - browser closes, session completely ends
                await browser.close()
                print("✅ Browser closed - session ended")
                
                # Wait 1-3 seconds for fresh start
                delay = random.uniform(1, 3)
                print(f"⏱️  Fresh start in {delay:.1f}s...")
                await asyncio.sleep(delay)
                
            except Exception as e:
                print(f"❌ Error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    print("🚀 Starting bot simulator...")
    print("🖱️  Using REAL OS mouse and keyboard events")
    print("📊 Scrolls WILL be detected by fingerprinting")
    print("🎯 39% click chance AFTER 15-20 seconds of natural behavior")
    print("🔄 Each session is completely fresh (browser closes)\n")
    asyncio.run(main())
