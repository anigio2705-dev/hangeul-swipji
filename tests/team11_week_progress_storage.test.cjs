/* Browserless regression for localStorage failure during seven-day quiz grading. */
const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'..','hangul-week.js'),'utf8');
function boot(allowWrite){
  const nodes=new Map();
  const make=tag=>({
    tag,children:[],style:{},dataset:{},attributes:{},_html:'',
    setAttribute(name,value){this.attributes[name]=value},
    append(...items){this.children.push(...items)},
    replaceChildren(...items){this.children=items},
    set innerHTML(value){this._html=value;this.children=[]},
    get innerHTML(){return this._html},
    textContent:''
  });
  const get=id=>{if(!nodes.has(id))nodes.set(id,make(id));return nodes.get(id)};
  let saved=null;
  const lessons=Array.from({length:7},(_,i)=>({
    id:'d'+(i+1),title:'Day '+(i+1),en:'practice',goal:'read',goalEn:'read',
    instruction:'practice',write:[],steps:[],practice:[],home:'repeat',ready:'review',
    quiz:[{prompt:'가를 고르세요',en:'choose',choices:['가','나'],answer:0,why:'가입니다'}]
  }));
  const context={
    window:{HSHangul:{stop(){},refreshBadges(){}},HSWeek:lessons,print(){}},
    document:{title:'',getElementById:get,createElement:make,querySelectorAll:()=>[]},
    location:{search:'?day=1',href:'https://example.test/hangul-week.html?day=1'},
    history:{replaceState(){}},URL,URLSearchParams,
    localStorage:{getItem:()=>null,setItem(_key,value){if(!allowWrite)throw Error('storage blocked');saved=value}}
  };
  vm.runInNewContext(source,context);
  const quiz=get('quiz').children[0];
  quiz.children[2].children[0].onclick();
  get('grade').onclick();
  return {get,stored:()=>saved};
}
test('blocked localStorage never shows a persisted completion badge',()=>{
  const {get,stored}=boot(false);
  assert.equal(stored(),null);
  assert.doesNotMatch(get('days').children[0].innerHTML,/✓/);
  assert.match(get('score').textContent,/진도 저장 실패/);
  get('days').children[1].onclick();
  assert.match(get('progress-label').textContent,/진도를 저장할 수 없습니다/);
  assert.doesNotMatch(get('days').children[0].innerHTML,/✓/);
});
test('successful localStorage write persists progress and displays completion',()=>{
  const {get,stored}=boot(true);
  assert.equal(JSON.parse(stored()).d1,true);
  assert.match(get('days').children[0].innerHTML,/✓/);
  assert.doesNotMatch(get('score').textContent,/저장 실패/);
});
