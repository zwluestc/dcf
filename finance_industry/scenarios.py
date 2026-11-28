"""Original fictional disclosures. Values and claims here stay on the author side."""
from datetime import date, timedelta
import hashlib
import random


def table(**rows):
    return "\n".join(f"| {label.replace('_', ' ')} | {value} |" for label, value in rows.items())


class Case:
    def __init__(self, kind, seed, variant):
        self.kind, self.variant = kind, variant
        self.r = random.Random(f"{seed}:{kind}:{variant}")
        self.suffix = hashlib.sha256(f"{seed}:{kind}:{variant}".encode()).hexdigest()[:8]
        self.id = f"{kind}-{self.suffix}"
        self.year = 2024 + variant % 2
        self.cutoff = date(self.year + 1, 4, 30)
        self.docs, self.claims = [], {}
        self.names = self.r.sample(["Cairn Vale", "Lark Sound", "Mica Basin", "Sorrel Bay",
                                    "Tarn Head", "Sable Inlet", "Opal Strand", "Alder Ness"], 3)
        # Counterbalance outcomes within pairs without a universal variant -> verdict mapping.
        self.regime=(variant + hashlib.sha256(f"{seed}:{kind}:regime".encode()).digest()[0])%2

    def doc(self, title, text, age, publisher):
        docid = self.r.randbytes(5).hex()
        self.docs.append(dict(id=docid, title=title, publisher=publisher, text=text,
                              date=(self.cutoff - timedelta(days=age)).isoformat(),
                              url=f"https://archive.invalid/{self.id}/{docid}"))
        return docid

    def claim(self, key, ask, value, *sources):
        self.claims[key] = dict(ask=ask, value=value, sources=sorted(sources))


def foundry(c):
    a, b, _ = c.names
    c.title = "晶圆代工：谁拿到了更多外部客户出货？"
    c.brief = f"比较 {a} 与 {b} 在 FY{c.year} 的外部客户晶圆出货，只看两家合计。两家以不同片径报告，集团内部调拨不属于可比市场。"
    doc = c.doc
    size = c.r.randrange(180, 230)
    x = size + (16 if c.regime else -16)
    y = size * 9 // 4
    intra, cons = c.r.randrange(24, 48), c.r.randrange(36, 74)
    da = doc(a+" | annual operating supplement", "FY close. Unit: thousand physical 300 mm wafers. Dispatches include transfers to the captive packaging subsidiary.\n"+table(Dispatches=x+intra,Captive_transfers=intra), 21, a)
    db = doc(b+" | audited fab statistics", "FY close. Unit: thousand physical 200 mm wafers. Bonded inventory moved to a group warehouse is not an external sale.\n"+table(Dispatches=y+cons,Group_warehouse=cons), 17, b)
    dm = doc("Wafer council | comparability bulletin", "Standardise by wafer area. One 200 mm wafer counts as 4/9 of a 300 mm wafer. Rank the two names on external shipments, not installed capacity.", 68, "Wafer council")
    doc(a+" | nameplate expansion", table(Nameplate_thousand_wafers=x+intra+130)+"\nAnnual capacity including the announced retrofit.", 5, a)
    doc(b+" | amended dispatches", table(Dispatches=y+cons+45,Group_warehouse=cons), -5, b)
    eq = y*4/9
    c.claim("a_external","第一家公司外部出货（千片，300 mm 当量）", x, da)
    c.claim("b_external","第二家公司外部出货（同单位）", eq, db, dm)
    c.claim("a_share_pct","第一家公司占两家可比出货的百分比", 100*x/(x+eq), da, db, dm)
    c.claim("leader","外部出货领先者（公司全称）", a if x>eq else b, da, db, dm)
    c.claim("physical_count_bias","直接按两种片径的原始外销量排名会偏向哪家公司（全称）", b, db, dm, da)


def retail(c):
    a=c.names[0]
    c.title="连锁零售：开店掩盖了老店下滑吗？"
    c.brief=f"为 {a} 的 FY{c.year} 业绩会准备简报。按审计口径桥接两年收入，对比全网增长与持续经营门店的增长。用同一货币，剔除两年不同时营业的门店。"
    base=c.r.randrange(320,450); change=c.r.randrange(14,32)*(-1 if c.regime==0 else 1)
    closed=c.r.randrange(24,45); new=closed+c.r.randrange(45,70)
    prev=base+closed; now=base+change+new
    d0=c.doc(a+" | prior year store accounts","Prior FY, currency millions, audited; stores closed before the current FY are included.\n"+table(Net_sales=prev),64,a)
    d1=c.doc(a+" | consolidated annual accounts","Current FY, currency millions, after returns and indirect taxes.\n"+table(Net_sales=now),11,a)
    dc=c.doc("Store estate | perimeter reconciliation","No relocations. Closures traded only in prior FY; openings only in current FY. Register shows NET SALES in currency THOUSANDS.\n"+table(Closures_prior=closed*1000,Openings_current=new*1000),10,a)
    c.doc("Trading update | headline till receipts","Preliminary, gross of sales taxes.\n"+table(Till_receipts=now+27),32,a)
    c.doc("Store estate | correction after board review",table(Openings_current=(new+8)*1000),-2,a)
    g=(now/prev-1)*100; s=100*change/base
    c.claim("reported_pct","审计口径全网同比增长率（%）",g,d0,d1)
    c.claim("comparable_pct","持续经营门店同比增长率（%）",s,d0,d1,dc)
    c.claim("gap_pp","全网减可比增长（百分点）",g-s,d0,d1,dc)
    c.claim("perimeter_net","开关店带来的净收入增量（百万）",new-closed,dc)
    c.claim("readthrough","结论：新店净贡献掩盖老店萎缩填 masked_contraction，否则填 comparable_growth", "masked_contraction" if change<0 else "comparable_growth",d0,d1,dc)


def wind(c):
    a,b,_=c.names
    c.title="海上风电：中标容量能否进入可融资项目清单？"
    c.brief=f"复核 {a} Renewables 的两处海上项目 {a} Bank 和 {b} Shoal。授标只是第一关；本行只纳入已授标且已签并网协议的权益容量。未签项目的权益容量单列。"
    mw1=c.r.randrange(42,67)*10; mw2=c.r.randrange(31,45)*10
    p1=c.r.choice([50,60,75]);p2=c.r.choice([40,55,80])
    signed=1 if c.regime==0 else 2
    aw=c.doc("Offshore round | final awards",f"Both {a} Bank (lot I) and {b} Shoal (lot II) received awards. MW gross, at turbine: \n"+table(Lot_I=mw1,Lot_II=mw2),35,"Coastal leasing office")
    cap=c.doc(a+" | JV interests","Voting rights differ from economic rights. Economic interests, percent:\n"+table(Lot_I=p1,Lot_II=p2),20,a+" Renewables")
    grid=c.doc("Interconnection | binding instruments register","As-of register, lists both awards. A reservation is nonbinding.\n"+table(Lot_I="executed" if signed==1 else "reservation",Lot_II="executed" if signed==2 else "reservation"),0,"Transmission operator")
    c.doc("Offshore round | developer presentation","Gross bid pipeline including unawarded options.\n"+table(Pipeline=mw1+mw2+300),6,a)
    c.doc("Interconnection | subsequent executions",table(Lot_I="executed",Lot_II="executed"),-4,"Transmission operator")
    one,two=mw1*p1/100,mw2*p2/100; banked,pending=(one,two) if signed==1 else (two,one)
    c.claim("awarded_gross","合计已授标毛容量（MW）",mw1+mw2,aw)
    c.claim("bankable_equity","纳入清单的权益容量（MW）",banked,aw,cap,grid)
    c.claim("watch_equity","待并网签署的权益容量（MW）",pending,aw,cap,grid)
    c.claim("conversion_pct","纳入清单占已授标权益容量的百分比",100*banked/(one+two),aw,cap,grid)
    c.claim("next_catalyst","应跟踪哪一地块的并网签署（I 或 II）","II" if signed==1 else "I",grid)


def smelter(c):
    a=c.names[0]
    c.title="铜冶炼：加工费重定价会不会吃掉契约缓冲？"
    c.brief=f"为 {a} Metals 的信贷委员会量化年度加工费重定价。只对浮动合同套用新费率；套保收益与其他抵消项假定为零。契约测试按冲击后的全年 EBITDA，比门槛低即 breach，否则 clear。"
    tonnes=c.r.randrange(75,101)*10000; floating=c.r.choice([30,40,50,60])
    old=c.r.randrange(63,76);new=c.r.randrange(23,38); fx=c.r.choice([6.8,7.1,7.2])
    ebitda=c.r.randrange(58,71)*10; loss=tonnes*floating/100*(old-new)*fx/1e6
    hurdle=round(ebitda-loss)+(15 if c.regime==0 else -15)
    vol=c.doc(a+" | feed contract register","Annual dry metric tonnes, no moisture adjustment.\n"+table(Dry_feed_tonnes=tonnes,Indexed_share_pct=floating),28,a)
    fee=c.doc("Smelter guild | settlement circular","Treatment charges received by the smelter, USD per dry tonne. The reset applies for the full year.\n"+table(Previous_rate=old,Reset_rate=new),3,"Smelter guild")
    debt=c.doc(a+" | lender sensitivity sheet","This is a fixed operating case. EBITDA and minimum are CNY millions; FX is CNY per USD.\n"+table(Base_EBITDA=ebitda,Minimum_EBITDA=hurdle,FX=fx),9,a+" Treasury")
    c.doc("Market wire | spot concentrate chatter","Indicative spot for discretionary shipments; not the annual contract settlement.\n"+table(Spot_charge=new-9),1,"Commodity wire")
    c.doc("Smelter guild | next negotiation",table(Reset_rate=new+12),-7,"Smelter guild")
    c.claim("exposed_tonnes","浮动合同干吨数",tonnes*floating/100,vol)
    c.claim("loss_usd_m","全年 EBITDA 减少额（百万美元，损失写正）",loss/fx,vol,fee)
    c.claim("post_cny_m","冲击后 EBITDA（百万人民币）",ebitda-loss,vol,fee,debt)
    c.claim("headroom_cny_m","契约缓冲（冲击后减门槛，百万人民币）",ebitda-loss-hurdle,vol,fee,debt)
    c.claim("test","契约测试结论：breach 或 clear","breach" if ebitda-loss<hurdle else "clear",vol,fee,debt)


def port(c):
    a=c.names[0]; y=c.year
    c.title="集装箱港口：修订后哪个季度的本地吞吐量最高？"
    c.brief=f"交易台认为 {a} 港 FY{y} 的峰值来自转运。核对港务局累计月报和关务复核，找出本地箱量（总吞吐减转运）的单季峰值。复核只改其指明的累计单元格，不得把修订额滚入后期累计。"
    base=c.r.randrange(150,205); q=[base-30,base+12,base+20,base-15]
    adjust=c.r.randrange(15,25)*(1 if c.regime==0 else -1)
    trans=[c.r.randrange(30,60) for _ in q]
    labels=["Q1","Q2","Q3","Q4"]
    run=lambda a:[sum(a[:i+1]) for i in range(len(a))]
    cum=run([v+t for v,t in zip(q,trans)]); t=run(trans)
    d=c.doc(a+" | port authority annual abstract","Year-to-date total throughput, THOUSAND TEU. Each column closes at the indicated quarter-end.\n"+table(**dict(zip(labels,cum))),29,a+" Port")
    e=c.doc(a+" | customs transshipment series","Year-to-date transshipment, THOUSAND TEU, same perimeter.\n"+table(**dict(zip(labels,t))),23,a+" Customs")
    rev=c.doc("Reconciliation | signed customs corrigendum","Replace ONLY the Q2 year-to-date transshipment observation. Later cumulative observations already incorporate all audit entries. Unit: TEU, not thousands.\n"+table(Q2_replacement=(t[1]+adjust)*1000),2,a+" Customs")
    c.doc(a+" | rail interchange","Landside boxes moved by rail, not incremental throughput.\n"+table(Q3=base+85),7,a+" Rail")
    c.doc("Customs | post-close abstract",table(Q2_replacement=t[1]*1000),-1,a+" Customs")
    final=q[:]; final[1]-=adjust;final[2]+=adjust
    peak=max(range(4),key=lambda i:final[i])
    c.claim("q2_local","修订后 Q2 单季本地箱量（千 TEU）",final[1],d,e,rev)
    c.claim("q3_local","修订后 Q3 单季本地箱量（千 TEU）",final[2],d,e,rev)
    c.claim("peak_quarter","修订后单季本地箱量最高季度（Q1 至 Q4）",labels[peak],d,e,rev)
    c.claim("peak_local","峰值单季本地箱量（千 TEU）",final[peak],d,e,rev)
    c.claim("annual_local","全年本地箱量（千 TEU，用年末累计）",sum(q),d,e)


def insurer(c):
    a,b,_=c.names; y=c.year+1
    c.title="保险并购：报价溢价与交易完成日能否同时确认？"
    c.brief=f"给事件团队还原 {a} Assurance 收购 {b} Life 的时间线。按最早正式公告指定的未受影响交易日收盘价，计算现金报价溢价。以交易所状态登记判定是否完成；批准、签约与交割的日期要分开。"
    price=c.r.randrange(180,275)/10; offer=price+c.r.randrange(18,49)/10
    announced=date(y,3,4); before=announced-timedelta(days=1)
    # Use a weekday for the unaffected close in both calendar years.
    while before.weekday()>4: before-=timedelta(days=1)
    closed=c.regime==1; completion=date(y,4,c.r.randrange(18,26))
    bid=c.doc(a+" | definitive bid notice",f"Cash-only signed agreement for {b} Life. Quote in cents per common share.\n"+table(Announcement=str(announced),Unaffected_date=str(before),Cash_cents=round(offer*100)),(c.cutoff-announced).days,a+" Assurance")
    tape=c.doc(b+" | exchange closing tape","Official tape in currency units per common share. Intraday highs are not closing prices.\n"+table(**{str(before)+" close":round(price,2),str(before)+" high":round(price+1.1,2),str(announced)+" close":round(offer-0.4,2)}),30,"Listing exchange")
    reg=c.doc("Insurance control | clearance order","Change of control approved. This order alone does not transfer title.\n"+table(Approval=str(date(y,4,11))),19,"Insurance supervisor")
    state=c.doc("Listing exchange | settlement register",f"Counterparties: {a} Assurance and {b} Life. Complete register as of cutoff.\n"+table(State="completed" if closed else "awaiting settlement",Title_transfer=str(completion) if closed else "not recorded"),0,"Listing exchange")
    c.doc("Deal press | expected timetable","Advisers targeted an early April closing. The target is indicative.",25,"Deal press")
    c.doc("Listing exchange | May transaction digest",table(State="completed",Title_transfer=str(completion) if closed else str(date(y,5,2))),-8,"Listing exchange")
    c.claim("cash_per_share","每股现金报价（货币单位，非分）",round(offer,2),bid)
    c.claim("premium_pct","相对未受影响收盘价的报价溢价（%）",100*(offer/price-1),bid,tape)
    c.claim("approval_date","监管批准日（ISO 日期）",str(date(y,4,11)),reg)
    c.claim("completion_date","已登记交割日（ISO 日期）；尚无记录填 unconfirmed",str(completion) if closed else "unconfirmed",state)
    c.claim("elapsed_days","从正式公告到交割经过的自然日数，不含起始日；尚未交割填 unconfirmed",(completion-announced).days if closed else "unconfirmed",*([bid,state] if closed else [state]))


def battery(c):
    a,b,h=c.names
    c.title="电池隔膜行业：本地供需缺口能否靠一条新线填平？"
    c.brief=f"为 {a} 地区产业组写下一财年的隔膜供需简报。区域基准仅计存量合格出货和已获客户认证的新线，下行情景撤去临时补贴带来的电芯需求。再判断尚待认证的 {h} 线单独获批后，基准缺口是否消失。供给减需求为正表示过剩；不考虑跨区贸易、库存或涨价反应。"
    base=c.r.randrange(34,48); subsidy=c.r.randrange(5,10)
    intensity=c.r.choice([1.6,1.8,2.0]); qualified=c.r.randrange(12,19)
    ramp=c.r.choice([50,60,75]); new=qualified*ramp/100
    pending=c.r.randrange(12,17); ramp2=c.r.choice([40,50,60])
    short=round(pending*ramp2/100 + (2.4 if c.regime else -2.4),2)
    carry=round((base+subsidy)*intensity-new-short,3)
    dem=c.doc(a+" | cell load outlook",f"Next FY regional cell production in GWh, net of exports. The independently funded base and incremental temporary-subsidy orders are additive.\n"+table(Funded_base=base,Subsidy_increment=subsidy),17,"Battery users council")
    use=c.doc("Qualification board | separator bill of materials","Effective regional weighted intensity, includes process scrap. Apply once to net cell output. Units: square metres per kWh of cells.\n"+table(Intensity=intensity),55,"Qualification board")
    stock=c.doc(a+" | incumbent supply census","Next FY salable separator shipments from existing plants, in THOUSAND square metres. New lines excluded; no further utilization haircut on this volume.\n"+table(Incumbent_shipments=round(carry*1000)),27,"Regional film association")
    line=c.doc("Projects desk | commissioning ledger",f"New lines at {b} (A) and {h} (B). Capacity in MILLION square metres. Ramp is next FY saleable output as percent of nameplate if qualified.\n"+table(A_nameplate=qualified,A_ramp_pct=ramp,B_nameplate=pending,B_ramp_pct=ramp2),13,"Projects desk")
    qual=c.doc("Qualification board | customer release docket",f"Commercial release at the cutoff: {b} (A) and {h} (B). Mechanical completion alone leaves customer acceptance outstanding.\n"+table(A="accepted",B="in testing"),0,"Qualification board")
    c.doc(h+" | plant celebration","The line is mechanically complete; press note quotes full nameplate capacity and first sample rolls.",3,h)
    c.doc("Qualification board | subsequent release",f"{h} (B) was accepted by its first customer this morning.",-3,"Qualification board")
    allrefs=(dem,use,stock,line,qual)
    c.claim("demand_m","基准需求（百万平方米）",(base+subsidy)*intensity,dem,use)
    c.claim("supply_m","可纳入基准的供给（百万平方米）",carry+new,stock,line,qual)
    c.claim("base_balance_m","基准供需余额（百万平方米，保留符号）",-short,*allrefs)
    c.claim("no_subsidy_balance_m","撤去临时补贴需求后的供需余额（同单位）",-short+subsidy*intensity,*allrefs)
    c.claim("release_balance_m","保留补贴且待认证线获批后的供需余额（同单位）",-short+pending*ramp2/100,*allrefs)
    c.claim("catalyst_readthrough","该线获批的含义：足以消除基准缺口填 closes_gap，否则填 residual_shortage","closes_gap" if pending*ramp2/100>=short else "residual_shortage",*allrefs)


KINDS={f.__name__:f for f in [foundry,retail,wind,smelter,port,insurer,battery]}
