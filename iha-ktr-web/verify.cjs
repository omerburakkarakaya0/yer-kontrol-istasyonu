const {chromium}=require('C:/Users/KARAKAYA/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const path=require('path');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1920,height:1124},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8765');
 await page.evaluate(()=>document.fonts.ready);
 fs.mkdirSync(path.join(__dirname,'screenshots'),{recursive:true});
 for(const [view,name] of [['flight','01-ucus'],['mission','02-gorev-planlama'],['vision','03-goruntuleme']]){
  await page.locator(`[data-view="${view}"]`).click();
  await page.locator('main img').first().waitFor();
  await page.evaluate(async()=>{await Promise.all([...document.images].map(i=>i.decode().catch(()=>{})))});
  const problems=await page.evaluate(()=>({broken:[...document.images].filter(i=>!i.naturalWidth).map(i=>i.src),overflow:[...document.querySelectorAll('.panel')].filter(e=>e.scrollHeight>e.clientHeight+2).map(e=>({heading:e.querySelector('h2')?.textContent,client:e.clientHeight,scroll:e.scrollHeight}))}));
  console.log(view,JSON.stringify(problems));
  await page.locator('#station').screenshot({path:path.join(__dirname,'screenshots',name+'.png')});
 }
 await page.locator('[data-view="flight"]').click();
 await page.locator('[data-mode="RTL"]').click();
 if((await page.locator('.mode-value').first().textContent())!=='RTL')throw Error('Mode control failed');
 await page.keyboard.press('2');if(await page.locator('.mission-layout').count()!==1)throw Error('View shortcut failed');
 await page.setViewportSize({width:1366,height:768});await page.keyboard.press('1');
 await page.screenshot({path:path.join(__dirname,'screenshots','kontrol-1366.png')});
 console.log('errors',errors);if(errors.length)process.exitCode=1;
 await browser.close();
})();
