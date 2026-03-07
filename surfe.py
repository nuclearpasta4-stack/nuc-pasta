import asyncio
import random
import time
import math
import requests
import psutil
from playwright.async_api import async_playwright
from pynput.mouse import Controller, Button
from pynput.keyboard import Controller as KeyboardController, Key

# Global controllers
mouse = Controller()
keyboard = KeyboardController()

class SimpleBotSimulator:
    def __init__(self, page=None):
        self.page = page
        self.has_clicked = False
        self.browser = None
        self.playwright = None
        
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
        
        self.playwright = playwright
        self.browser = await playwright.chromium.launch(
            headless=False,
            proxy=proxy_config,
            args=['--disable-blink-features=AutomationControlled']
        )
        return self.browser

    async def force_kill_browser(self):
        """Force kill all Chrome processes to ensure complete cleanup"""
        try:
            if self.browser:
                await self.browser.close()
                self.browser = None
            
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                    
            print("✅ Browser processes fully terminated")
        except Exception as e:
            print(f"Error during browser cleanup: {e}")
        await asyncio.sleep(1)

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
        """Create realistic page length based on desired session time"""
        # Get viewport height
        viewport_height = await self.page.evaluate("window.innerHeight")
        
        # We want session to be 25-40 seconds total
        # At 50px/sec reading speed, we need 1250-2000px of content
        target_content = random.randint(1400, 2200)
        
        # FIXED: Properly formatted JavaScript string
        await self.page.evaluate(f"""
            // Remove any existing spacers
            const oldSpacer = document.getElementById('scroll-spacer');
            if (oldSpacer) oldSpacer.remove();
            
            // Check current page height
            const currentHeight = document.body.scrollHeight;
            
            // Calculate needed height - FIXED: using proper variable name
            const viewportH = {viewport_height};
            const targetContent = {target_content};
            const needed = Math.max(0, targetContent - currentHeight + viewportH);
            
            if (needed > 100) {{
                var spacer = document.createElement('div');
                spacer.id = 'scroll-spacer';
                spacer.style.height = needed + 'px';
                spacer.style.width = '1px';
                spacer.style.opacity = '0';
                document.body.appendChild(spacer);
                console.log(`Added ${{needed}}px scroll spacer for ${{targetContent}}px content`);
            }}
        """)
        
        # Return the actual page height after adding spacer
        final_height = await self.page.evaluate("document.body.scrollHeight")
        return final_height

    async def human_scroll(self, current_position=None, target_position=None):
        """Smooth, natural scrolling with realistic speed"""
        
        if target_position is None:
            # Just do a natural scroll chunk
            direction = random.choice(['down', 'down', 'down', 'up'])  # 75% down
            scroll_amount = random.randint(200, 500)
            
            if direction == 'up':
                scroll_amount = -scroll_amount
            target_position = (current_position or 0) + scroll_amount
        else:
            # Scroll to specific target
            if current_position is None:
                current_position = await self.page.evaluate("window.scrollY")
            scroll_amount = target_position - current_position
        
        if abs(scroll_amount) < 50:
            return  # Don't scroll tiny amounts
        
        # Get max scroll to prevent overshooting
        max_scroll = await self.page.evaluate("document.body.scrollHeight - window.innerHeight")
        target_position = max(0, min(max_scroll, target_position))
        scroll_amount = target_position - current_position
        
        if abs(scroll_amount) < 50:
            return
        
        # Calculate realistic scroll speed (40-70 pixels per second)
        pixels_per_second = random.uniform(40, 70)
        scroll_duration = abs(scroll_amount) / pixels_per_second
        
        # Break into steps for smoothness (15-25 steps per second)
        steps = max(5, int(scroll_duration * random.uniform(15, 25)))
        
        # Determine scroll direction
        if scroll_amount > 0:
            scroll_func = lambda: mouse.scroll(0, -1)  # down
            step_pixels = scroll_amount / steps
        else:
            scroll_func = lambda: mouse.scroll(0, 1)   # up
            step_pixels = abs(scroll_amount) / steps
        
        # Perform smooth scroll
        for i in range(steps):
            clicks_this_step = max(1, int(step_pixels / 40))  # ~40px per click
            
            for _ in range(clicks_this_step):
                scroll_func()
                await asyncio.sleep(random.uniform(0.02, 0.04))
            
            # Variable pause between steps (simulates natural acceleration)
            if i < steps - 1:
                pause = scroll_duration / steps * random.uniform(0.7, 1.3)
                await asyncio.sleep(pause)
        
        # Natural pause after scrolling (reading time)
        if random.random() < 0.7:
            read_pause = random.uniform(0.8, 2.2)
            await asyncio.sleep(read_pause)

    async def find_clickable_elements(self):
        """Find anything clickable on the page"""
        elements = await self.page.evaluate("""
            () => {
                const clickables = [];
                
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
        await asyncio.sleep(random.uniform(0.5, 1.5))

    async def run_session(self):
        """Main session loop with realistic timing based on content"""
        print("🌐 Loading page...")
        await self.page.goto('https://pk.vpsmail.name.ng/ad2.html', wait_until='domcontentloaded')
        
        # Create realistic scroll space and get actual page height
        page_height = await self.create_scroll_space()
        
        # Wait for ad to load
        await asyncio.sleep(2)
        
        # Get viewport height for calculations
        viewport_height = await self.page.evaluate("window.innerHeight")
        content_height = page_height - viewport_height
        
        # Calculate realistic session duration
        min_read_speed = 45
        max_read_speed = 65
        
        base_reading_seconds = content_height / random.uniform(min_read_speed, max_read_speed)
        
        # Add extra time for interactions
        extra_time = random.uniform(13, 22)
        
        session_duration = base_reading_seconds + extra_time
        session_end = time.time() + session_duration
        
        # Track when we can first click (after 60-70% of session)
        click_time = time.time() + (session_duration * random.uniform(0.6, 0.7))
        
        last_scroll = time.time()
        last_hover = time.time()
        total_scroll = 0
        up_scrolls = 0
        
        print(f"\n📄 Content height: {content_height:.0f}px")
        print(f"📖 Reading speed: {content_height/base_reading_seconds:.1f} px/sec")
        print(f"⏱️  Session duration: {session_duration:.1f}s")
        print(f"🖱️  Click possible after: {((click_time - time.time())):.1f}s")
        print(f"📊 Click probability: 3%\n")
        
        while time.time() < session_end:
            now = time.time()
            
            # Check current scroll position
            current_scroll_y = await self.page.evaluate("window.scrollY")
            max_scroll = await self.page.evaluate("document.body.scrollHeight - window.innerHeight")
            
            # Determine if we should scroll
            scroll_interval = random.uniform(4, 8)
            if now - last_scroll > scroll_interval:
                # Decide scroll direction based on position
                if current_scroll_y < 100:
                    # Near top - scroll down
                    target_y = random.randint(300, min(800, max_scroll))
                    direction = "down"
                elif current_scroll_y > max_scroll - 200:
                    # Near bottom - scroll up (re-read)
                    target_y = random.randint(max(0, max_scroll - 600), max_scroll - 200)
                    direction = "up"
                    up_scrolls += 1
                else:
                    # Middle - 70% down, 30% up
                    if random.random() < 0.7:
                        target_y = min(max_scroll, current_scroll_y + random.randint(200, 600))
                        direction = "down"
                    else:
                        target_y = max(0, current_scroll_y - random.randint(200, 500))
                        direction = "up"
                        up_scrolls += 1
                
                scroll_amount = abs(target_y - current_scroll_y)
                total_scroll += scroll_amount
                
                print(f"📜 Scrolling {direction} ({scroll_amount}px) - at {current_scroll_y:.0f}/{max_scroll:.0f}")
                await self.human_scroll(current_scroll_y, target_y)
                last_scroll = now
            
            # Check for click opportunity
            if now >= click_time and not self.has_clicked:
                clickables = await self.find_clickable_elements()
                
                if clickables and random.random() < 0.03:
                    target = random.choice(clickables)
                    
                    # Scroll to element if needed
                    current_y = await self.page.evaluate("window.scrollY")
                    if abs(target['y'] - current_y) > 200:
                        await self.human_scroll(current_y, target['y'] - 100)
                    
                    await self.human_mouse_move(target['x'], target['y'])
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                    mouse.click(Button.left)
                    print(f"✅ CLICKED: {target['type']}")
                    self.has_clicked = True
                    await asyncio.sleep(random.uniform(1.5, 2.5))
            
            # Hover occasionally
            hover_interval = random.uniform(3, 6)
            if now - last_hover > hover_interval:
                await self.random_hover()
                last_hover = now
            
            await asyncio.sleep(0.5)
        
        # Session summary
        print(f"\n📊 Session Summary:")
        print(f"   - Duration: {session_duration:.1f}s")
        print(f"   - Total scroll: {total_scroll:.0f}px")
        print(f"   - Scroll speed: {total_scroll/session_duration:.1f} px/sec")
        print(f"   - Up scrolls: {up_scrolls}")
        if self.has_clicked:
            print(f"   - Click: YES (3% chance)")

async def run_single_session(session_num):
    """Run a single complete session with full cleanup"""
    print(f"\n{'='*50}")
    print(f"🔄 SESSION #{session_num} STARTING")
    print(f"{'='*50}")
    
    async with async_playwright() as p:
        simulator = None
        browser = None
        
        try:
            simulator = SimpleBotSimulator()
            browser = await simulator.setup_browser(p)
            context = await browser.new_context(viewport={'width': 1280, 'height': 720})
            page = await context.new_page()
            simulator.page = page
            
            await simulator.run_session()
            await simulator.force_kill_browser()
            print("✅ Browser completely terminated - session fully ended")
            
        except Exception as e:
            print(f"❌ Error in session: {e}")
            if simulator:
                await simulator.force_kill_browser()
    
    await asyncio.sleep(1)

async def main():
    try:
        import psutil
    except ImportError:
        print("Installing psutil...")
        import subprocess
        subprocess.check_call(['pip', 'install', 'psutil'])
        import psutil
    
    session_count = 0
    
    print("🚀 Starting bot simulator...")
    print("📜 REALISTIC scrolling based on content length")
    print("⏱️  Session time = reading speed (45-65px/sec) + interactions")
    print("🎯 3% click chance at 60-70% of session")
    print("🔄 Fresh browser each session\n")
    
    while True:
        session_count += 1
        await run_single_session(session_count)
        delay = random.uniform(1, 3)
        print(f"⏱️  Next session in {delay:.1f}s...\n")
        await asyncio.sleep(delay)

if __name__ == "__main__":
    asyncio.run(main())
