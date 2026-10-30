(function(){
'use strict';
if(window.__HS_SITE_LANGUAGE_V3__)return;window.__HS_SITE_LANGUAGE_V3__=true;
var KEY='hs-site-language',languages=[['ko','한국어'],['en','English'],['ja','日本語'],['es','Español'],['zh-CN','简体中文'],['ru','Русский'],['mn','Монгол'],['vi','Tiếng Việt']];
var params=new URLSearchParams(location.search),valid=new Set(languages.map(function(x){return x[0]})),requested=params.get('lang'),saved='';
try{saved=localStorage.getItem(KEY)||localStorage.getItem('hs-language')||''}catch(e){}
var lang=valid.has(requested)?requested:valid.has(saved)?saved:'ko';
// A legacy saved language outside the approved eight must not persist in navigation.
if(saved&&!valid.has(saved)){try{localStorage.removeItem(KEY);localStorage.removeItem('hs-language');localStorage.removeItem('hs-translation-language')}catch(e){}}
function store(code){try{localStorage.setItem(KEY,code);localStorage.setItem('hs-language',code);localStorage.setItem('hs-translation-language',code)}catch(e){}}
function cookie(code){var val=code==='ko'?'/ko/ko':'/ko/'+code;document.cookie='googtrans='+val+';path=/;SameSite=Lax';}
var UI_MESSAGES={
ko:{loading:'번역을 불러오는 중…',unreviewed:'기계 번역 · 정확성 미검수',unavailable:'자동 번역을 사용할 수 없습니다. 브라우저 번역을 이용해 주세요.',error:'번역 연결 실패. 브라우저 번역을 이용해 주세요.'},
en:{loading:'Loading translation…',unreviewed:'Machine translation · Not reviewed',unavailable:'Translation unavailable. Please use browser translation.',error:'Translation connection failed. Please use browser translation.'},
ja:{loading:'翻訳を読み込んでいます…',unreviewed:'機械翻訳 · 未確認',unavailable:'翻訳を利用できません。ブラウザーの翻訳機能をご利用ください。',error:'翻訳に接続できません。ブラウザーの翻訳機能をご利用ください。'},
es:{loading:'Cargando traducción…',unreviewed:'Traducción automática · Sin revisar',unavailable:'Traducción no disponible. Utilice la traducción del navegador.',error:'Error de conexión de traducción. Utilice su navegador.'},
'zh-CN':{loading:'正在加载翻译…',unreviewed:'机器翻译 · 未经审核',unavailable:'翻译不可用，请使用浏览器翻译。',error:'翻译连接失败，请使用浏览器翻译。'},
ru:{loading:'Загрузка перевода…',unreviewed:'Машинный перевод · Не проверен',unavailable:'Перевод недоступен. Используйте перевод в браузере.',error:'Не удалось подключить перевод. Используйте браузер.'},
mn:{loading:'Орчуулга ачаалж байна…',unreviewed:'Машин орчуулга · Шалгаагүй',unavailable:'Орчуулга боломжгүй. Хөтчийн орчуулгыг ашиглана уу.',error:'Орчуулгын холболт амжилтгүй. Хөтчийн орчуулгыг ашиглана уу.'},
vi:{loading:'Đang tải bản dịch…',unreviewed:'Dịch máy · Chưa được kiểm duyệt',unavailable:'Không có bản dịch. Vui lòng dùng chức năng dịch của trình duyệt.',error:'Không thể kết nối dịch thuật. Vui lòng dùng trình duyệt.'}
};
function message(key){return (UI_MESSAGES[lang]||UI_MESSAGES.en)[key]}
function status(s){var el=document.getElementById('hs-language-status');if(el)el.textContent=s;var headerStatus=document.getElementById('hs-header-language-status');if(headerStatus)headerStatus.textContent=s}
function addStyle(){if(document.getElementById('hs-site-language-css'))return;var style=document.createElement('style');style.id='hs-site-language-css';style.textContent='#hs-site-language-bar{position:fixed!important;right:12px!important;bottom:12px!important;z-index:2147483640!important;display:flex!important;align-items:center!important;gap:7px!important;max-width:calc(100vw - 24px)!important;background:#fff!important;color:#152b42!important;border:1px solid #d7e1ec!important;border-radius:14px!important;padding:8px 10px!important;box-shadow:0 6px 25px #0b244130!important;font:600 12px -apple-system,BlinkMacSystemFont,"Noto Sans KR",sans-serif!important}#hs-site-language-bar label{white-space:nowrap!important;font-size:12px!important}#hs-site-language-bar select{max-width:160px!important;min-width:112px!important;background:white!important;color:#17324c!important;border:1px solid #c6d5e4!important;border-radius:8px!important;padding:8px 6px!important;font-size:13px!important}#hs-language-status{position:absolute;bottom:100%;right:0;max-width:270px;background:#fff;color:#3b556d;border-radius:9px;padding:6px 10px;font-size:11px;box-shadow:0 3px 10px #0002}#hs-language-status:empty{display:none}#hs-google-translate-host{position:absolute;left:-9999px;top:-9999px;visibility:hidden}body{top:0!important}.goog-te-banner-frame,.skiptranslate iframe{display:none!important}@media(max-width:760px){#hs-site-language-bar{right:8px!important;bottom:8px!important;padding:6px 7px!important;gap:5px!important;border-radius:10px!important}#hs-site-language-bar label{font-size:11px!important}#hs-site-language-bar select{font-size:12px!important;min-width:104px!important;max-width:130px!important;padding:7px 4px!important}}';document.head.appendChild(style)}
function attach(){
addStyle();var bar=document.getElementById('hs-site-language-bar');if(!bar){bar=document.createElement('div');bar.id='hs-site-language-bar';bar.className='notranslate';bar.setAttribute('translate','no');bar.innerHTML='<label for="hs-site-language-select">🌐 언어 / Language</label><select id="hs-site-language-select" aria-label="Website language"></select><div id="hs-language-status" role="status"></div>';document.body.appendChild(bar)}
var existingSelect=document.getElementById('language')||document.getElementById('lang');
// Some course pages have a complete, native Korean/English renderer. Keep it
// authoritative for those two languages instead of overriding its state.
var nativeBilingual=!!(existingSelect&&typeof existingSelect.onchange==='function'&&Array.from(existingSelect.options||[]).some(function(o){return o.value==='en'}));
// Other supported languages use explicitly labelled machine translation.
// Preserve the language being studied when translating the surrounding interface.
document.querySelectorAll('#consonants,#vowels,#syllables,.board,[data-sound],#selected-syllable,#selected-formula').forEach(function(el){el.classList.add('notranslate');el.setAttribute('translate','no')});if(existingSelect){bar.style.setProperty('display','none','important');var headerStatus=document.createElement('p');headerStatus.id='hs-header-language-status';headerStatus.setAttribute('role','status');headerStatus.className='notranslate';headerStatus.style.cssText='margin:0;padding:0 16px;font-size:12px;color:#795322;max-width:100%';(existingSelect.closest('header')||existingSelect.parentElement).appendChild(headerStatus)}
var labels={ko:'언어',en:'Language',ja:'言語',es:'Idioma','zh-CN':'语言',ru:'Язык',mn:'Хэл',vi:'Ngôn ngữ'};var label=bar.querySelector('label');if(label)label.textContent='🌐 '+labels[lang];
var select=document.getElementById('hs-site-language-select');select.replaceChildren();languages.forEach(function(x){var o=document.createElement('option');o.value=x[0];o.textContent=x[1];select.appendChild(o)});select.value=lang;
function go(code){if(!valid.has(code))return;store(code);cookie(code);var url=new URL(location.href);url.searchParams.set('lang',code);url.searchParams.set('translate_version','4');location.assign(url.toString())}
select.addEventListener('change',function(){go(select.value)});
var desktop=document.getElementById('language')||document.getElementById('lang');
if(desktop){var nativeOptions=Array.from(desktop.options||[]);if(nativeOptions.length){languages.forEach(function(x){if(!nativeOptions.some(function(o){return o.value===x[0]})){var opt=document.createElement('option');opt.value=x[0];opt.textContent=x[1];desktop.appendChild(opt)}});Array.from(desktop.options).forEach(function(o){if(!valid.has(o.value))o.remove()});desktop.value=lang;desktop.addEventListener('change',function(e){var code=desktop.value;if(!valid.has(code))return;
if(nativeBilingual&&(code==='ko'||code==='en')&&(lang==='ko'||lang==='en')){lang=code;store(code);cookie(code);select.value=code;return}
e.stopImmediatePropagation();go(code)},true)}}
document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[href]');if(!a)return;try{var u=new URL(a.href,location.href);if(u.origin===location.origin&&(u.pathname.endsWith('.html')||u.pathname.endsWith('/'))){u.searchParams.set('lang',lang);a.href=u.href}}catch(err){}},true);
document.querySelectorAll('a[href]').forEach(function(a){var raw=a.getAttribute('href');if(!raw||raw[0]==='#'||/^(mailto:|tel:|javascript:)/i.test(raw))return;try{var u=new URL(raw,location.href);if(u.origin===location.origin&&(u.pathname.endsWith('.html')||u.pathname.endsWith('/'))){u.searchParams.set('lang',lang);a.href=u.href}}catch(e){}});
if(nativeBilingual&&(lang==='ko'||lang==='en')){
  existingSelect.value=lang;existingSelect.onchange({target:existingSelect});
  cookie(lang);status('');return;
}
if(lang==='ko'){cookie('ko');status('');return}
cookie(lang);status(message('loading'));
var host=document.createElement('div');host.id='hs-google-translate-host';host.className='notranslate';document.body.appendChild(host);
window.hsGoogleTranslateReady=function(){try{new google.translate.TranslateElement({pageLanguage:'ko',includedLanguages:languages.filter(function(x){return x[0]!=='ko'}).map(function(x){return x[0]}).join(','),autoDisplay:false},'hs-google-translate-host');var n=0;var timer=setInterval(function(){n++;var combo=document.querySelector('.goog-te-combo');if(combo){clearInterval(timer);combo.value=lang;combo.dispatchEvent(new Event('change',{bubbles:true}));status(message('unreviewed'))}else if(n>35){clearInterval(timer);status(message('unavailable'))}},200)}catch(e){status(message('error'))}};
var script=document.createElement('script');script.src='https://translate.google.com/translate_a/element.js?cb=hsGoogleTranslateReady';script.async=true;script.onerror=function(){status(message('error'))};document.head.appendChild(script);
}
store(lang);document.documentElement.lang=lang;document.documentElement.dir=['ar','ur','fa','he'].includes(lang)?'rtl':'ltr';
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',attach,{once:true});else attach();
})();