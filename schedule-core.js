/* =========================================================
   美顏針預約 · 共用排程邏輯（純函式，讀 config.js 的 CONFIG；無個資、會 push 上 GitHub）
   ★ 使用頁面：index.html（公開）、admin.html／Yanice.local.html（本機）。
   ★ 必須在 config.js 之後載入。改本檔要 bump index.html 的 schedule-core.js?v=（pre-commit hook 會把關）。
   ★ 門診表.html 的 regularSessions 是「診次」語意（早診＝整個健保診），刻意不共用本檔。
   ========================================================= */
const WD_NAMES = ['日','一','二','三','四','五','六'];

function ymd(d){
  return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
}

// 週日 11:00 長期固定約在該日是否成立（未過截止日、不在 skip、不在休診日）
function sundayFixedActive(iso){
  if(!CONFIG.sundayMorningFixed) return false;
  const end = CONFIG.sundayMorningFixedEndDate;
  if(end && iso > end) return false;
  if((CONFIG.sundayMorningSkip||[]).includes(iso)) return false;
  if((CONFIG.daysOff||[]).includes(iso)) return false;
  return true;
}

// 回傳某日門診：{loc, slots:[{key,label,copy,pending?}]} 或 null（無診），不含休假判斷
function clinicForDate(d){
  const wd = d.getDay();           // 0=日 .. 6=六
  const iso = ymd(d);
  const friAfter = iso >= CONFIG.fridayToLinkouDate;   // 週五是否已轉林口
  const satAfter = iso >= CONFIG.saturdayExtraDate;     // 週六是否已加下午+晚上
  let loc=null, slots=[];

  if(wd===1){ loc='龜山'; slots=[{key:'13:55',label:'13:55',copy:'13:55'}]; }            // 一
  else if(wd===4){ loc='龜山'; slots=[{key:'17:15',label:'17:15',copy:'17:15'}]; }       // 四
  else if(wd===5){ loc = friAfter?'林口':'龜山'; slots=[{key:'09:00',label:'早上',copy:'早上 (09:00 - 12:00)'}]; } // 五
  else if(wd===0){ loc='林口'; slots=[{key:'11:00',label:'11:00',copy:'11:00'},{key:'13:55',label:'13:55',copy:'13:55'}]; } // 日
  else if(wd===6){                                                                       // 六
    loc='龜山';
    const monthStr = iso.substring(0,7);
    if(CONFIG.saturdayMorningDates.includes(iso)){
      slots.push({key:'09:00',label:'09:00',copy:'09:00'});
    } else if((CONFIG.saturdayMorningPendingMonths||[]).includes(monthStr)){
      slots.push({key:'09:00',label:'待定',copy:'',pending:true});
    }
    if(satAfter){ slots.push({key:'13:55',label:'13:55',copy:'13:55'}); slots.push({key:'17:15',label:'17:15',copy:'17:15'}); }
    if(slots.length===0) return null;
  } else {
    return null;
  }
  // 特例加開時段：併入當日並依時間排序
  const extras = CONFIG.extraSlots ? CONFIG.extraSlots.filter(e=>e.date===iso) : [];
  if(extras.length){
    extras.forEach(e=> slots.push({key:e.slot,label:e.label,copy:e.copy}));
    slots.sort((a,b)=> a.key<b.key ? -1 : (a.key>b.key?1:0));
  }
  const closed = CONFIG.closedSlots || [];
  slots = slots.filter(s=> !closed.includes(iso+'|'+s.key));
  return {loc, slots};
}

// 個別患者提早報到：回傳調整後時間字串或 null（僅該患者專屬連結套用）
function earlyTimeFor(who, wd, slot){
  const rules = (CONFIG.earlyArrival||{})[who];
  if(!rules) return null;
  const r = rules.find(x=> x.slot===slot && (x.wd===undefined || x.wd===wd));
  return r ? r.time : null;
}

function isBooked(iso, key, wd){
  if(wd===0 && key==='11:00' && sundayFixedActive(iso)) return true;
  return CONFIG.bookings.some(b=>b.date===iso && b.slot===key);
}
