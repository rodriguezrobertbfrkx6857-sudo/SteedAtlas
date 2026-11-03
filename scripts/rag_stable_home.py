"""Same-browser original homepage comparison after its entrance animations settle."""
import json

from paths import ROOT
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

shots=ROOT/'reports/screenshots/rag-upgrade'
measurements=[]
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    for device,width,height in [('desktop',1440,1000),('mobile',390,844)]:
        for mode in ('baseline','current'):
            page=browser.new_page(viewport={'width':width,'height':height},reduced_motion='reduce')
            if mode=='baseline':page.route('**/evidence-adapter.js',lambda route:route.fulfill(body='',content_type='text/javascript'))
            page.goto('http://127.0.0.1:5175/',wait_until='networkidle')
            page.wait_for_timeout(2500)
            assert page.locator('#steedatlas-evidence').count()==0
            page.screenshot(path=str(shots/f'stable-{mode}-home-{device}.png'))
            page.close()
        a=Image.open(shots/f'stable-baseline-home-{device}.png').convert('RGB')
        b=Image.open(shots/f'stable-current-home-{device}.png').convert('RGB')
        changed=sum(1 for pixel in ImageChops.difference(a,b).getdata() if max(pixel)>20)
        measurements.append({'device':device,'pixel_difference_fraction_gt20':changed/(width*height)})
    browser.close()
report={'method':'Same original assets, enhancement script disabled for control; entrance animations settled 2.5 seconds',
        'measurements':measurements}
(ROOT/'reports/rag-upgrade/stable-home.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
