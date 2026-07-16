"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  createChart, IChartApi, ISeriesApi, ColorType, CrosshairMode,
  LineSeries, CandlestickSeries, AreaSeries, HistogramSeries, Time,
} from "lightweight-charts";

interface PricePoint { date: string; close: number; open?: number; high?: number; low?: number; volume?: number }
type ChartMode = "candle" | "mountain" | "line";
type IndicatorId = "sma20"|"sma50"|"sma200"|"ema20"|"ema50"|"bb"|"rsi"|"macd"|"volume";

interface IndDef { id: IndicatorId; label: string; group: string }
const INDICATORS: IndDef[] = [
  {id:"volume",label:"Hacim",group:"Temel"},
  {id:"sma20",label:"SMA 20",group:"Hareketli Ortalamalar"},{id:"sma50",label:"SMA 50",group:"Hareketli Ortalamalar"},{id:"sma200",label:"SMA 200",group:"Hareketli Ortalamalar"},
  {id:"ema20",label:"EMA 20",group:"Hareketli Ortalamalar"},{id:"ema50",label:"EMA 50",group:"Hareketli Ortalamalar"},
  {id:"bb",label:"Bollinger Bantları",group:"Volatilite"},
  {id:"rsi",label:"RSI (14)",group:"Momentum"},{id:"macd",label:"MACD",group:"Momentum"},
];
const MODES=[{k:"candle"as const,l:"MUM"},{k:"mountain"as const,l:"DAĞ"},{k:"line"as const,l:"ÇİZGİ"}];
const PERIODS=[{k:"1d",l:"1G"},{k:"5d",l:"5G"},{k:"1mo",l:"1A"},{k:"3mo",l:"3A"},{k:"6mo",l:"6A"},{k:"1y",l:"1Y"}];
const INTERVALS=[{k:"1m",l:"1D"},{k:"3m",l:"3D"},{k:"5m",l:"5D"},{k:"15m",l:"15"},{k:"30m",l:"30"},{k:"1h",l:"1S"},{k:"4h",l:"4S"},{k:"1d",l:"G"}];

// ── Teknik hesaplama ──
function sma(d:number[],p:number):(number|null)[]{const o:(number|null)[]=[];for(let i=0;i<d.length;i++){if(i<p-1){o.push(null);continue}let s=0;for(let j=i-p+1;j<=i;j++)s+=d[j];o.push(s/p)}return o}
function ema(d:number[],p:number):(number|null)[]{const o:(number|null)[]=[];const k=2/(p+1);for(let i=0;i<d.length;i++){if(i===0){o.push(d[0]);continue}const pr=o[i-1]??d[i];o.push(d[i]*k+pr*(1-k))}return o}
function bollinger(d:number[],p:number,m:number){const mid=sma(d,p);const up:(number|null)[]=[];const lo:(number|null)[]=[];for(let i=0;i<d.length;i++){if(i<p-1){up.push(null);lo.push(null);continue}let s=0;for(let j=i-p+1;j<=i;j++)s+=(d[j]-mid[i]!)**2;const std=Math.sqrt(s/p);up.push(mid[i]!+m*std);lo.push(mid[i]!-m*std)}return{upper:up,middle:mid,lower:lo}}
function rsiFn(d:number[],p:number):(number|null)[]{const o:(number|null)[]=[];let ag=0,al=0;for(let i=1;i<d.length;i++){const ch=d[i]-d[i-1];const gn=ch>0?ch:0;const ls=ch<0?-ch:0;if(i<p){ag+=gn;al+=ls;if(i!==p-1){o.push(null);continue}ag/=p;al/=p}else{ag=(ag*(p-1)+gn)/p;al=(al*(p-1)+ls)/p}o.push(al===0?100:100-(100/(1+ag/al)))}return o}
function macdFn(d:number[]){const e12=ema(d,12);const e26=ema(d,26);const mv:(number|null)[]=[];for(let i=0;i<d.length;i++)mv.push(e12[i]!=null&&e26[i]!=null?e12[i]!-e26[i]!:null);const sig=ema(mv.filter(v=>v!=null)as number[],9);const ps:(number|null)[]=[];const off=26+9-2;for(let i=0;i<d.length;i++)ps.push(i<off?null:sig[i-off]??null);const hs:(number|null)[]=[];for(let i=0;i<d.length;i++)hs.push(mv[i]!=null&&ps[i]!=null?mv[i]!-ps[i]!:null);return{macd:mv,signal:ps,hist:hs}}

const resolveColor = (c:string)=>{const m=c.match(/^var\((--[^,)]+)/);if(m){const v=getComputedStyle(document.documentElement).getPropertyValue(m[1]).trim();if(v)return v}return c.includes("green")?"#22C55E":c.includes("red")?"#EF4444":"#9CA3AF"};
const isLight = ()=>document.documentElement.getAttribute("data-theme")==="light";

export default function PriceChart({data,color,period,interval,onPeriodChange,onIntervalChange}:{
  data:PricePoint[];color:string;period?:string;interval?:string;
  onPeriodChange?:(p:string)=>void;onIntervalChange?:(i:string)=>void;
}){
  const cRef=useRef<HTMLDivElement>(null);
  const chRef=useRef<IChartApi|null>(null);
  const mainRef=useRef<ISeriesApi<"Candlestick"|"Line"|"Area">|null>(null);
  const indRefs=useRef<Map<string,ISeriesApi<"Line">|ISeriesApi<"Histogram">>>(new Map());
  const seenRef=useRef<Map<number,number>>(new Map());
  const [mode,setMode]=useState<ChartMode>("candle");
  const [ready,setReady]=useState(false);
  const [leg,setLeg]=useState({o:0,h:0,l:0,c:0,v:0});
  const [inds,setInds]=useState<Set<IndicatorId>>(new Set(["volume"]));
  const [showInd,setShowInd]=useState(false);
  const [showAn,setShowAn]=useState(false);
  const [analysis,setAnalysis]=useState<string|null>(null);
  const [anLoad,setAnLoad]=useState(false);

  if(!data||data.length<2)return <div className="rounded-sm border p-8 text-center" style={{borderColor:"var(--term-border)",backgroundColor:"var(--term-panel)"}}><div className="text-xs font-mono mb-1" style={{color:"var(--term-muted)"}}>Bu dönem/aralık için veri yok</div><div className="text-[10px] font-mono" style={{color:"var(--term-muted)"}}>Daha geniş dönem veya büyük aralık dene</div></div>;

  const toTime = (d:PricePoint):Time=>{let t=Math.floor(new Date(d.date+(d.date.includes("T")?"":"T00:00:00")).getTime()/1000);const s=seenRef.current.get(t)||0;seenRef.current.set(t,s+1);return(t+s)as Time};

  // Memoize derived data
  const closes=useMemo(()=>data.map(d=>d.close),[data]);
  const trend=useMemo(()=>data.length>=2?(data[data.length-1].close>=data[0].close?"up":"down"):"up",[data]);
  const base=useMemo(()=>color||(trend==="up"?"var(--term-green)":"var(--term-red)"),[color,trend]);
  const lineColor=useMemo(()=>base.startsWith("var(")?resolveColor(base):base,[base]);

  const toggleInd=(id:IndicatorId)=>{setInds(p=>{const n=new Set(p);n.has(id)?n.delete(id):n.add(id);return n})};

  const handleAnalyze=async()=>{
    setAnLoad(true);setShowAn(true);setAnalysis(null);
    try{
      const r=rsiFn(closes,14).filter(v=>v!=null)as number[];
      const lastR=r.length?r[r.length-1]:null;
      const m=macdFn(closes);
      const lm=m.macd.filter(v=>v!=null).pop();
      const ls=m.signal.filter(v=>v!=null).pop();
      const lh=m.hist.filter(v=>v!=null).pop();
      const s20=sma(closes,20).filter(v=>v!=null)as number[];
      const s50=sma(closes,50).filter(v=>v!=null)as number[];
      const lp=closes[closes.length-1];
      const cp=closes.length>=2?((closes[closes.length-1]-closes[closes.length-2])/closes[closes.length-2]*100):0;
      const hi=Math.max(...data.map(d=>d.high??d.close));
      const lo=Math.min(...data.map(d=>d.low??d.close));
      const parts=[`█ TEKNİK ANALİZ RAPORU`,` `,`Fiyat: $${lp.toFixed(2)} | Değişim: ${cp>=0?"+":""}${cp.toFixed(2)}%`,`Dönem Yüksek: $${hi.toFixed(2)} | Dönem Düşük: $${lo.toFixed(2)}`,` `,`── RSI (14) ──`,`Değer: ${lastR!=null?lastR.toFixed(1):"—"}`,lastR!=null?(lastR>70?"⚠ Satış bölgesi (aşırı alım)":lastR<30?"⚡ Alış bölgesi (aşırı satım)":"→ Nötr bölge"):"",` `,`── MACD ──`,`MACD: ${lm?.toFixed(4)??"—"} | Sinyal: ${ls?.toFixed(4)??"—"}`,lh!=null?`Histogram: ${lh>=0?"+":""}${lh.toFixed(4)} ${lh>=0?"(yükseliş)":"(düşüş)"}`:"",` `,`── Hareketli Ortalamalar ──`,`SMA 20: $${s20.length?s20[s20.length-1].toFixed(2):"—"}`,lp>s20[s20.length-1]?"✓ Fiyat SMA 20 üzerinde":s20.length?"✗ Fiyat SMA 20 altında":"",`SMA 50: $${s50.length?s50[s50.length-1].toFixed(2):"—"}`,lp>s50[s50.length-1]?"✓ Fiyat SMA 50 üzerinde":s50.length?"✗ Fiyat SMA 50 altında":"",s20.length&&s50.length?(s20[s20.length-1]>s50[s50.length-1]?"✓ Golden Cross":"✗ Death Cross"):"",` `,lastR!=null&&lastR<30&&s20.length&&lp>s20[s20.length-1]?"📈 Dip alım fırsatı (aşırı satım + SMA üstü)":lastR!=null&&lastR>70?"📉 Düzeltme riski (aşırı alım)":lh!=null&&lh>0&&lp>(s20.slice(-1)[0]??0)?"📈 Pozitif trend":"→ Belirsiz, izlemeye devam",` `,`⚠ Yatırım tavsiyesi değildir.`];
      setAnalysis(parts.filter(Boolean).join("\n"));
    }catch{setAnalysis("Analiz başarısız")}
    setAnLoad(false);
  };

  const fmt=(n:number|string)=>Number(n).toFixed(2);
  const fmtV=(n:number)=>n>=1e6?`${(n/1e6).toFixed(1)}M`:n>=1e3?`${(n/1e3).toFixed(1)}K`:`${n}`;

  // Chart creation (mount only)
  useEffect(()=>{if(!cRef.current)return;const L=isLight();const ch=createChart(cRef.current,{width:cRef.current.clientWidth,height:420,layout:{background:{type:ColorType.Solid,color:"transparent"},textColor:L?"#334155":"#94A3B8",fontSize:11,fontFamily:"IBM Plex Mono, JetBrains Mono, monospace"},grid:{vertLines:{visible:false},horzLines:{color:L?"#E2E8F0":"#1E293B",style:1}},crosshair:{mode:CrosshairMode.Normal,vertLine:{color:"#64748B",style:3,width:1,visible:true,labelVisible:false},horzLine:{color:"#64748B",style:3,width:1,visible:true,labelVisible:false}},rightPriceScale:{borderColor:L?"#CBD5E1":"#334155",borderVisible:true,scaleMargins:{top:.08,bottom:.20}},timeScale:{borderColor:L?"#CBD5E1":"#334155",borderVisible:true,timeVisible:false,fixLeftEdge:true,fixRightEdge:true}});
    chRef.current=ch;setReady(true);
    const ro=new ResizeObserver(e=>{for(const{contentRect:{width}}of e){if(width>0)ch.applyOptions({width})}});ro.observe(cRef.current);
    const mo=new MutationObserver(()=>{const l=isLight();ch.applyOptions({layout:{textColor:l?"#334155":"#94A3B8"},grid:{horzLines:{color:l?"#E2E8F0":"#1E293B"}},rightPriceScale:{borderColor:l?"#CBD5E1":"#334155"},timeScale:{borderColor:l?"#CBD5E1":"#334155"}})});
    mo.observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
    ch.subscribeCrosshairMove(p=>{if(!p.time||!p.point)return;const d=data.find(x=>toTime(x)===p.time);if(d)setLeg({o:d.open??d.close,h:d.high??d.close,l:d.low??d.close,c:d.close,v:d.volume??0})});
    return ()=>{ro.disconnect();mo.disconnect();ch.remove()};
  },[]);

  // Series + indicators (mode/interval/inds changes)
  useEffect(()=>{if(!chRef.current||!ready)return;const ch=chRef.current;
    seenRef.current.clear();
    if(mainRef.current){ch.removeSeries(mainRef.current);mainRef.current=null}
    indRefs.current.forEach(s=>ch.removeSeries(s));indRefs.current.clear();
    let s: ISeriesApi<"Candlestick"> | ISeriesApi<"Area"> | ISeriesApi<"Line">;
    if(mode==="candle"){s=ch.addSeries(CandlestickSeries,{upColor:"#26A69A",downColor:"#EF5350",borderUpColor:"#26A69A",borderDownColor:"#EF5350",wickUpColor:"#26A69A",wickDownColor:"#EF5350",priceLineVisible:false});s.setData(data.map(d=>({time:toTime(d),open:d.open??d.close,high:d.high??d.close,low:d.low??d.close,close:d.close})))}
    else if(mode==="mountain"){s=ch.addSeries(AreaSeries,{lineColor,lineWidth:2,topColor:lineColor+"55",bottomColor:lineColor+"04",priceLineVisible:false});s.setData(data.map(d=>({time:toTime(d),value:d.close})))}
    else{s=ch.addSeries(LineSeries,{color:lineColor,lineWidth:2,lastValueVisible:true,priceLineVisible:false,crosshairMarkerBackgroundColor:lineColor});s.setData(data.map(d=>({time:toTime(d),value:d.close})))}
    mainRef.current=s;

    const al=(id:string,vals:(number|null)[],c:string,lw:1|2|3|4)=>{const se=ch.addSeries(LineSeries,{color:c,lineWidth:lw,priceLineVisible:false,lastValueVisible:true});se.setData(vals.map((v,i)=>({time:toTime(data[i]),value:v??0})).filter(x=>x.value!==0||vals[0]!=null));indRefs.current.set(id,se)};
    if(inds.has("sma20"))al("sma20",sma(closes,20),"#F59E0B",1);
    if(inds.has("sma50"))al("sma50",sma(closes,50),"#3B82F6",1);
    if(inds.has("sma200"))al("sma200",sma(closes,200),"#EC4899",1);
    if(inds.has("ema20"))al("ema20",ema(closes,20),"#F59E0B",1);
    if(inds.has("ema50"))al("ema50",ema(closes,50),"#3B82F6",1);

    if(inds.has("volume")){const vo=ch.addSeries(HistogramSeries,{priceFormat:{type:"volume"},priceScaleId:"volume",priceLineVisible:false});ch.priceScale("volume").applyOptions({scaleMargins:{top:.82,bottom:0},borderVisible:false});vo.setData(data.map(d=>({time:toTime(d),value:d.volume??0,color:(d.close>=(d.open??d.close)?"#26A69A55":"#EF535055")})));indRefs.current.set("volume",vo)}

    if(inds.has("bb")){const{upper,middle,lower}=bollinger(closes,20,2);
      [["bb_u","#A78BFA",upper]as const,["bb_m","#C4B5FD",middle]as const,["bb_l","#A78BFA",lower]as const].forEach(([id,c,v])=>{const se=ch.addSeries(LineSeries,{color:c,lineWidth:1,priceLineVisible:false,lastValueVisible:true});se.setData(v.map((x,i)=>({time:toTime(data[i]),value:x??0})).filter(x=>x.value!==0));indRefs.current.set(id,se)})}

    if(inds.has("rsi")){const r=rsiFn(closes,14);const rs=ch.addSeries(LineSeries,{color:"#A855F7",lineWidth:1,priceScaleId:"rsi",priceLineVisible:false,lastValueVisible:true});rs.setData(r.map((v,i)=>({time:toTime(data[i]),value:v??0})).filter(x=>x.value!==0));ch.priceScale("rsi").applyOptions({scaleMargins:{top:.80,bottom:.05},borderVisible:false});indRefs.current.set("rsi",rs);
      ["#EF444433","#22C55E33"].forEach((c,i)=>{const rf=ch.addSeries(LineSeries,{color:c,lineWidth:1,lineStyle:2,priceScaleId:"rsi",priceLineVisible:false,lastValueVisible:false});rf.setData(data.map(d=>({time:toTime(d),value:i===0?70:30})));indRefs.current.set(`rsi_r${i}`,rf)})}

    if(inds.has("macd")){const{macd:mv,signal:sig,hist:hs}=macdFn(closes);
      const ms=ch.addSeries(LineSeries,{color:"#F59E0B",lineWidth:1,priceScaleId:"macd",priceLineVisible:false,lastValueVisible:true});ms.setData(mv.map((v,i)=>({time:toTime(data[i]),value:v??0})).filter(x=>x.value!==0));
      const ss=ch.addSeries(LineSeries,{color:"#3B82F6",lineWidth:1,priceScaleId:"macd",priceLineVisible:false,lastValueVisible:true});ss.setData(sig.map((v,i)=>({time:toTime(data[i]),value:v??0})).filter(x=>x.value!==0));
      const hSer=ch.addSeries(HistogramSeries,{priceScaleId:"macd",priceLineVisible:false});hSer.setData(hs.map((v,i)=>({time:toTime(data[i]),value:v??0,color:(v??0)>=0?"#22C55E55":"#EF444455"})).filter(x=>x.value!==0));
      ch.priceScale("macd").applyOptions({scaleMargins:{top:.85,bottom:.02},borderVisible:false});indRefs.current.set("macd_m",ms);indRefs.current.set("macd_s",ss);indRefs.current.set("macd_h",hSer)}

    // Apply dynamic timeVisible based on interval
    ch.applyOptions({timeScale:{timeVisible:interval==="1d"}});
    // fitContent only on mode/indicator change, not on data refresh
    ch.timeScale().fitContent();
    const last=data[data.length-1];setLeg({o:last.open??last.close,h:last.high??last.close,l:last.low??last.close,c:last.close,v:last.volume??0});
  },[mode,ready,interval,inds]);

  // Data refresh only — no fitContent (preserves user zoom)
  useEffect(()=>{if(!mainRef.current||!ready)return;seenRef.current.clear();const s=mainRef.current;
    if(mode==="candle")(s as ISeriesApi<"Candlestick">).setData(data.map(d=>({time:toTime(d),open:d.open??d.close,high:d.high??d.close,low:d.low??d.close,close:d.close})));
    else(s as unknown as ISeriesApi<"Line"|"Area">).setData(data.map(d=>({time:toTime(d),value:d.close})));
  },[data]);

  const groups=new Map<string,IndDef[]>();INDICATORS.forEach(d=>{const a=groups.get(d.group)??[];a.push(d);groups.set(d.group,a)});

  return <div className="rounded-sm border" style={{borderColor:"var(--term-border)",backgroundColor:"var(--term-panel)"}}>
    <div className="flex items-center gap-4 px-3 py-2 border-b" style={{borderColor:"var(--term-border)"}}>
      {[["O",leg.o],["Y",leg.h],["D",leg.l],["K",leg.c]].map(([l,v])=><div key={l} className="flex items-center gap-1.5"><span className="font-mono text-[10px] tracking-wider" style={{color:"var(--term-muted)"}}>{l}</span><span className="font-mono text-xs font-semibold" style={{color:"var(--term-text)"}}>{fmt(v)}</span></div>)}
      <div className="flex items-center gap-1.5 ml-auto"><span className="font-mono text-[10px]" style={{color:"var(--term-muted)"}}>HACİM</span><span className="font-mono text-xs font-semibold" style={{color:"var(--term-text)"}}>{fmtV(leg.v)}</span></div>
    </div>
    <div ref={cRef} className="w-full"/>
    <div className="flex flex-wrap items-center gap-1 px-3 py-2 border-t" style={{borderColor:"var(--term-border)"}}>
      {MODES.map(m=><button key={m.k} onClick={()=>setMode(m.k)} className="font-mono text-[10px] tracking-wider px-2.5 py-1 rounded-sm transition-none" style={{color:mode===m.k?"var(--term-bg)":"var(--term-muted)",backgroundColor:mode===m.k?"var(--term-amber)":"transparent",border:"1px solid "+(mode===m.k?"var(--term-amber)":"var(--term-border)")}}>{m.l}</button>)}
      <span className="mx-1" style={{color:"var(--term-border)"}}>|</span>
      {onPeriodChange&&PERIODS.map(p=><button key={p.k} onClick={()=>onPeriodChange(p.k)} className="font-mono text-[10px] px-2 py-1 rounded-sm transition-none" style={{color:period===p.k?"var(--term-amber)":"var(--term-muted)",fontWeight:period===p.k?600:400,backgroundColor:period===p.k?"var(--term-amber)15":"transparent"}}>{p.l}</button>)}
      <span className="mx-1" style={{color:"var(--term-border)"}}>|</span>
      {onIntervalChange&&INTERVALS.map(i=><button key={i.k} onClick={()=>onIntervalChange(i.k)} className="font-mono text-[10px] px-2 py-1 rounded-sm transition-none" style={{color:interval===i.k?"var(--term-amber)":"var(--term-muted)",fontWeight:interval===i.k?600:400,backgroundColor:interval===i.k?"var(--term-amber)15":"transparent"}}>{i.l}</button>)}
      <span className="mx-1" style={{color:"var(--term-border)"}}>|</span>
      <div className="relative">
        <button onClick={()=>setShowInd(!showInd)} className="font-mono text-[10px] tracking-wider px-2.5 py-1 rounded-sm transition-none" style={{border:"1px solid var(--term-border)",color:showInd?"var(--term-amber)":"var(--term-muted)",backgroundColor:showInd?"var(--term-amber)15":"transparent"}}>⚙ INDIKATÖRLER</button>
        {showInd&&<div className="absolute bottom-full left-0 mb-1 w-56 rounded-sm z-50 p-2 space-y-1.5" style={{border:"1px solid var(--term-border)",backgroundColor:"var(--term-panel)",boxShadow:"0 8px 24px rgba(0,0,0,0.3)"}}>
          {[...groups.entries()].map(([grp,items])=><div key={grp}><div className="text-[9px] font-mono tracking-wider pb-1" style={{color:"var(--term-muted)"}}>{grp}</div>{items.map(ind=><label key={ind.id} className="flex items-center gap-2 py-0.5 cursor-pointer text-xs font-mono" style={{color:"var(--term-text)"}}><input type="checkbox" checked={inds.has(ind.id)} onChange={()=>toggleInd(ind.id)} style={{accentColor:"var(--term-amber)"}}/>{ind.label}</label>)}</div>)}
        </div>}
      </div>
      <div className="flex-1"/>
      <button onClick={handleAnalyze} disabled={anLoad} className="font-mono text-[10px] tracking-wider px-2.5 py-1 rounded-sm transition-none disabled:opacity-40" style={{border:"1px solid var(--term-amber)",color:"var(--term-amber)"}}>{anLoad?"ANALİZ…":"▶ GRAFİĞİ ANALİZ ET"}</button>
    </div>
    {showAn&&analysis&&<div className="border-t px-4 py-3 max-h-80 overflow-y-auto" style={{borderColor:"var(--term-border)"}}>
      <div className="flex items-center justify-between mb-2"><span className="font-mono text-[10px] tracking-wider" style={{color:"var(--term-muted)"}}>TEKNİK ANALİZ RAPORU</span><button onClick={()=>setShowAn(false)} className="font-mono text-xs transition-none" style={{color:"var(--term-muted)"}}>✕</button></div>
      <pre className="text-[11px] font-mono leading-relaxed whitespace-pre-wrap" style={{color:"var(--term-text)"}}>{analysis}</pre>
    </div>}
  </div>;
}
