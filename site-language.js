(function(){
'use strict';
if(window.__HS_SITE_LANGUAGE_V3__)return;window.__HS_SITE_LANGUAGE_V3__=true;
var KEY='hs-site-language',languages=[["ko", "한국어"], ["en", "English"], ["ja", "日本語"], ["es", "Español"], ["ru", "Русский"], ["zh-CN", "简体中文"], ["mn", "Монгол"], ["vi", "Tiếng Việt"]];
var params=new URLSearchParams(location.search),valid=new Set(languages.map(function(x){return x[0]})),requested=params.get('lang'),saved='';
try{saved=localStorage.getItem(KEY)||localStorage.getItem('hs-language')||''}catch(e){}
var lang=valid.has(requested)?requested:valid.has(saved)?saved:'ko';
function store(code){try{localStorage.setItem(KEY,code);localStorage.setItem('hs-language',code);localStorage.setItem('hs-translation-language',code)}catch(e){}}
function cookie(code){var val=code==='ko'?'/ko/ko':'/ko/'+code;document.cookie='googtrans='+val+';path=/;SameSite=Lax';}
function status(s){var el=document.getElementById('hs-language-status');if(el)el.textContent=s;var headerStatus=document.getElementById('hs-header-language-status');if(headerStatus)headerStatus.textContent=s}
function addStyle(){if(document.getElementById('hs-site-language-css'))return;var style=document.createElement('style');style.id='hs-site-language-css';style.textContent='#hs-site-language-bar{position:fixed!important;right:12px!important;bottom:12px!important;z-index:2147483640!important;display:flex!important;align-items:center!important;gap:7px!important;max-width:calc(100vw - 24px)!important;background:#fff!important;color:#152b42!important;border:1px solid #d7e1ec!important;border-radius:14px!important;padding:8px 10px!important;box-shadow:0 6px 25px #0b244130!important;font:600 12px -apple-system,BlinkMacSystemFont,"Noto Sans KR",sans-serif!important}#hs-site-language-bar label{white-space:nowrap!important;font-size:12px!important}#hs-site-language-bar select{max-width:160px!important;min-width:112px!important;background:white!important;color:#17324c!important;border:1px solid #c6d5e4!important;border-radius:8px!important;padding:8px 6px!important;font-size:13px!important}#hs-language-status{position:absolute;bottom:100%;right:0;max-width:270px;background:#fff;color:#3b556d;border-radius:9px;padding:6px 10px;font-size:11px;box-shadow:0 3px 10px #0002}#hs-language-status:empty{display:none}#hs-google-translate-host{position:absolute;left:-9999px;top:-9999px;visibility:hidden}body{top:0!important}.goog-te-banner-frame,.skiptranslate iframe{display:none!important}@media(max-width:760px){#hs-site-language-bar{right:8px!important;bottom:8px!important;padding:6px 7px!important;gap:5px!important;border-radius:10px!important}#hs-site-language-bar label{font-size:11px!important}#hs-site-language-bar select{font-size:12px!important;min-width:104px!important;max-width:130px!important;padding:7px 4px!important}}';document.head.appendChild(style)}
function attach(){
addStyle();var bar=document.getElementById('hs-site-language-bar');if(!bar){bar=document.createElement('div');bar.id='hs-site-language-bar';bar.className='notranslate';bar.setAttribute('translate','no');bar.innerHTML='<label for="hs-site-language-select">🌐 언어 / Language</label><select id="hs-site-language-select" aria-label="Website language"></select><div id="hs-language-status" role="status"></div>';document.body.appendChild(bar)}
var existingSelect=document.getElementById('language')||document.getElementById('lang');
var nativeBilingual=!!(existingSelect&&typeof existingSelect.onchange==='function'&&Array.from(existingSelect.options).some(function(o){return o.value==='en'}));
// Preserve the language being studied when translating the surrounding interface.
document.querySelectorAll('#content,#skillArea,#lessonTitle,#lessonDesc,#recallPanel,#lessonCoach,#story,#translation,#questions,#legacy-source,#lesson,#consonants,#vowels,#syllables').forEach(function(el){el.classList.add('notranslate');el.setAttribute('translate','no')});if(existingSelect){bar.style.setProperty('display','none','important');var headerStatus=document.createElement('p');headerStatus.id='hs-header-language-status';headerStatus.setAttribute('role','status');headerStatus.className='notranslate';headerStatus.style.cssText='margin:0;padding:0 16px;font-size:12px;color:#795322;max-width:100%';(existingSelect.closest('header')||existingSelect.parentElement).appendChild(headerStatus)}
var select=document.getElementById('hs-site-language-select');select.replaceChildren();languages.forEach(function(x){var o=document.createElement('option');o.value=x[0];o.textContent=x[1];select.appendChild(o)});select.value=lang;
function go(code){if(!valid.has(code))return;store(code);cookie('ko');var url=new URL(location.href);url.searchParams.set('lang',code);url.searchParams.set('translate_version','4');location.assign(url.toString())}
select.addEventListener('change',function(){go(select.value)});
var desktop=document.getElementById('language')||document.getElementById('lang');
if(desktop){var nativeOptions=Array.from(desktop.options||[]);if(nativeOptions.length){languages.forEach(function(x){if(!nativeOptions.some(function(o){return o.value===x[0]})){var opt=document.createElement('option');opt.value=x[0];opt.textContent=x[1];desktop.appendChild(opt)}});Array.from(desktop.options).forEach(function(o){o.hidden=!valid.has(o.value);o.disabled=!valid.has(o.value)});desktop.value=lang;desktop.addEventListener('change',function(e){var code=desktop.value;if(!valid.has(code))return;if(nativeBilingual&&(code==='ko'||code==='en')){lang=code;store(code);cookie('ko');var u=new URL(location.href);u.searchParams.set('lang',code);history.replaceState(null,'',u);document.documentElement.lang=code;status('');return}e.stopImmediatePropagation();go(code)},true);if(nativeBilingual&&(lang==='ko'||lang==='en'))desktop.onchange({target:desktop})}}
document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[href]');if(!a)return;try{var u=new URL(a.href,location.href);if(u.origin===location.origin&&(u.pathname.endsWith('.html')||u.pathname.endsWith('/'))){u.searchParams.set('lang',lang);a.href=u.href}}catch(err){}},true);
document.querySelectorAll('a[href]').forEach(function(a){var raw=a.getAttribute('href');if(!raw||raw[0]==='#'||/^(mailto:|tel:|javascript:)/i.test(raw))return;try{var u=new URL(raw,location.href);if(u.origin===location.origin&&(u.pathname.endsWith('.html')||u.pathname.endsWith('/'))){u.searchParams.set('lang',lang);a.href=u.href}}catch(e){}});
if(lang==='ko'||(nativeBilingual&&lang==='en')){cookie('ko');status('');return}
// Keep third-party scripts out of the learning/account page. The native
// classroom languages and bilingual course handlers above remain local.
cookie('ko');
var messages={
 en:['Translate public page ↗','Machine translation opens in a new tab. Use this tab for lessons and your account. You can also use your browser’s translation.'],
 ja:['公開ページを翻訳 ↗','機械翻訳は新しいタブで開きます。授業とアカウントはこのタブで利用してください。ブラウザの翻訳も利用できます。'],
 es:['Traducir página pública ↗','La traducción automática se abre en otra pestaña. Usa esta pestaña para clases y tu cuenta. También puedes usar la traducción del navegador.'],
 ru:['Перевести открытую страницу ↗','Машинный перевод откроется в новой вкладке. Уроки и аккаунт доступны в этой вкладке. Также можно использовать перевод браузера.'],
 'zh-CN':['翻译公开页面 ↗','机器翻译将在新标签页中打开。课程和账户请在当前标签页使用。也可使用浏览器翻译。'],
 mn:['Нийтийн хуудсыг орчуулах ↗','Машин орчуулга шинэ табд нээгдэнэ. Хичээл болон бүртгэлээ энэ табаас ашиглана уу. Хөтчийн орчуулгыг мөн ашиглаж болно.'],
 vi:['Dịch trang công khai ↗','Bản dịch máy mở trong thẻ mới. Hãy dùng thẻ này cho lớp học và tài khoản. Bạn cũng có thể dùng bản dịch của trình duyệt.']
};
var copy=messages[lang]||messages.en;
var output=document.getElementById('hs-header-language-status')||document.getElementById('hs-language-status');
output.replaceChildren();
var localHost=/^(localhost|127\.|0\.0\.0\.0$|\[?::1\]?$)/i.test(location.hostname)||location.hostname.endsWith('.localhost');
if((location.protocol==='https:'||location.protocol==='http:')&&!localHost){
 var publicUrl=new URL(location.pathname,location.origin);publicUrl.searchParams.set('lang',lang);
 var link=document.createElement('a');link.id='hs-public-translation';link.textContent=copy[0];
 var translationUrl=new URL('https://translate.google.com/translate');
 translationUrl.searchParams.set('sl','ko');translationUrl.searchParams.set('tl',lang);translationUrl.searchParams.set('u',publicUrl.href);
 link.href=translationUrl.href;link.target='_blank';link.rel='noopener noreferrer';link.referrerPolicy='no-referrer';
 output.append(link,document.createTextNode(' · '+copy[1]));
}else{
 output.textContent='브라우저의 페이지 번역을 이용해 주세요. / Use your browser’s page translation.';
}

}
store(lang);document.documentElement.lang=lang;document.documentElement.dir=['ar','ur','fa','he'].includes(lang)?'rtl':'ltr';
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',attach,{once:true});else attach();
})();