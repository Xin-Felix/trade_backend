"""数据源注册表种子数据。

启动时将所有接口信息写入 data_sources 表（按 provider + api_name 检查，已存在跳过）。
支持多 provider：Tushare / AKShare / 自定义。
"""

from sqlalchemy.orm import Session

from app.models.data_source import DataSource


# ============================================================
# Tushare 数据源种子
# 格式: (api_name, title, category, description, proxy_path, doc_url, has_local_table, local_table_name)
# ============================================================

_TUSHARE_SEED_DATA = [
    # ====== ETF 专题 ======
    ("etf_basic", "ETF基本信息", "ETF专题", "获取国内ETF基础信息", "/api/v1/ts/etf-basic", "https://tushare.pro/wctapi/documents/385.md", 0, None),
    ("etf_index", "ETF跟踪指数", "ETF专题", "获取ETF基准指数列表信息", "/api/v1/ts/etf-index", "https://tushare.pro/wctapi/documents/386.md", 0, None),
    ("etf_share_size", "ETF份额规模", "ETF专题", "获取沪深ETF每日份额和规模数据", "/api/v1/ts/etf-share-size", "https://tushare.pro/wctapi/documents/408.md", 0, None),
    ("etf_sh_cons", "每日篮子组合(沪市PCF)", "ETF专题", "获取上交所ETF每日盘前披露的一篮子组合信息", "/api/v1/ts/etf-sh-cons", "https://tushare.pro/wctapi/documents/471.md", 0, None),
    ("etf_sz_cons", "每日篮子组合(深市PCF)", "ETF专题", "获取深交所ETF每日盘前披露的一篮子组合信息", "/api/v1/ts/etf-sz-cons", "https://tushare.pro/wctapi/documents/472.md", 0, None),
    ("etf_mins", "ETF历史分钟", "ETF专题", "获取ETF分钟数据", "/api/v1/ts/etf-mins", "https://tushare.pro/wctapi/documents/387.md", 0, None),
    ("rt_etf_k", "ETF实时日线", "ETF专题", "获取ETF实时日k线行情", "/api/v1/ts/rt-etf-k", "https://tushare.pro/wctapi/documents/400.md", 0, None),
    ("rt_etf_min", "ETF实时分钟", "ETF专题", "获取ETF实时分钟数据", "/api/v1/ts/rt-etf-min", "https://tushare.pro/wctapi/documents/416.md", 0, None),
    ("rt_etf_min_daily", "ETF实时分钟-日累计", "ETF专题", "获取ETF实时分钟数据日累计", "/api/v1/ts/rt-etf-min-daily", "https://tushare.pro/wctapi/documents/470.md", 0, None),
    ("rt_etf_sz_iopv", "ETF实时参考(深市)", "ETF专题", "ETF实时净值和申购赎回数据参考", "/api/v1/ts/rt-etf-sz-iopv", "https://tushare.pro/wctapi/documents/454.md", 0, None),
    ("idx_anns", "指数公司公告", "ETF专题", "获取指数公司披露的相关公告信息", "/api/v1/ts/idx-anns", "https://tushare.pro/wctapi/documents/460.md", 0, None),
    ("fund_daily", "ETF日线行情", "ETF专题", "获取ETF行情每日收盘后成交数据", "/api/v1/ts/fund-daily", "https://tushare.pro/wctapi/documents/127.md", 0, None),
    ("fund_adj", "ETF复权因子", "ETF专题", "获取基金复权因子", "/api/v1/ts/fund-adj", "https://tushare.pro/wctapi/documents/199.md", 0, None),
    # ====== 股票基础/行情 ======
    ("stock_basic", "股票列表", "股票数据,基础数据", "获取基础信息数据", "/api/v1/ts/stock-basic", "https://tushare.pro/wctapi/documents/25.md", 1, "stock_basic"),
    ("trade_cal", "交易日历", "股票数据,基础数据", "获取各大交易所交易日历数据", "/api/v1/ts/trade-cal", "https://tushare.pro/wctapi/documents/26.md", 0, None),
    ("daily", "历史日线", "股票数据,行情数据", "获取股票行情数据", "/api/v1/ts/daily", "https://tushare.pro/wctapi/documents/27.md", 1, "stock_daily"),
    ("weekly", "周线行情", "股票数据,行情数据", "获取A股周线行情", "/api/v1/ts/weekly", "https://tushare.pro/wctapi/documents/144.md", 1, "stock_weekly"),
    ("monthly", "月线行情", "股票数据,行情数据", "获取A股月线数据", "/api/v1/ts/monthly", "https://tushare.pro/wctapi/documents/145.md", 1, "stock_monthly"),
    ("adj_factor", "复权因子", "股票数据,行情数据", "获取股票复权因子", "/api/v1/ts/adj-factor", "https://tushare.pro/wctapi/documents/28.md", 0, None),
    ("daily_basic", "每日指标", "股票数据,行情数据", "获取全部股票每日重要基本面指标", "/api/v1/ts/daily-basic", "https://tushare.pro/wctapi/documents/32.md", 1, "stock_daily_basic"),
    ("pro_bar", "复权行情", "股票数据,行情数据", "获取前后复权日线数据", "/api/v1/ts/pro-bar", "https://tushare.pro/wctapi/documents/146.md", 0, None),
    ("suspend_d", "每日停复牌信息", "股票数据,行情数据", "按日期获取股票每日停复牌信息", "/api/v1/ts/suspend-d", "https://tushare.pro/wctapi/documents/214.md", 0, None),
    ("stk_limit", "每日涨跌停价格", "股票数据,行情数据", "获取全市场每日涨跌停价格", "/api/v1/ts/stk-limit", "https://tushare.pro/wctapi/documents/183.md", 1, "stock_limit"),
    ("namechange", "股票曾用名", "股票数据,基础数据", "历史名称变更记录", "/api/v1/ts/namechange", "https://tushare.pro/wctapi/documents/100.md", 0, None),
    ("stk_premarket", "每日股本(盘前)", "股票数据,基础数据", "每日开盘前获取当日股票股本情况", "/api/v1/ts/stk-premarket", "https://tushare.pro/wctapi/documents/329.md", 0, None),
    ("stk_weekly_monthly", "周月线行情(每日更新)", "股票数据,行情数据", "股票周/月线行情(每日更新)", "/api/v1/ts/stk-weekly-monthly", "https://tushare.pro/wctapi/documents/336.md", 0, None),
    ("stk_week_month_adj", "周月线复权行情", "股票数据,行情数据", "股票周/月线复权行情(每日更新)", "/api/v1/ts/stk-week-month-adj", "https://tushare.pro/wctapi/documents/365.md", 0, None),
    ("stk_mins", "历史分钟", "股票数据,行情数据", "获取A股分钟数据", "/api/v1/ts/stk-mins", "https://tushare.pro/wctapi/documents/370.md", 0, None),
    ("rt_min", "实时分钟", "股票数据,行情数据", "获取全A股票实时分钟数据", "/api/v1/ts/rt-min", "https://tushare.pro/wctapi/documents/374.md", 0, None),
    ("rt_k", "实时日线", "股票数据,行情数据", "获取实时日k线行情", "/api/v1/ts/rt-k", "https://tushare.pro/wctapi/documents/372.md", 0, None),
    ("rt_min_daily", "A股实时分钟-日累计", "股票数据,行情数据", "获取A股当日盘中历史分钟数据", "/api/v1/ts/rt-min-daily", "https://tushare.pro/wctapi/documents/457.md", 0, None),
    ("bak_daily", "备用行情", "股票数据,行情数据", "获取备用行情数据", "/api/v1/ts/bak-daily", "https://tushare.pro/wctapi/documents/255.md", 0, None),
    ("ggt_daily", "港股通每日成交统计", "股票数据,行情数据", "获取港股通每日成交信息", "/api/v1/ts/ggt-daily", "https://tushare.pro/wctapi/documents/196.md", 0, None),
    ("hsgt_top10", "沪深股通十大成交股", "股票数据,行情数据", "获取沪股通、深股通每日前十大成交详细数据", "/api/v1/ts/hsgt-top10", "https://tushare.pro/wctapi/documents/48.md", 0, None),
    ("ggt_top10", "港股通十大成交股", "股票数据,行情数据", "获取港股通每日成交数据", "/api/v1/ts/ggt-top10", "https://tushare.pro/wctapi/documents/49.md", 0, None),
    # ====== 财务数据 ======
    ("fina_indicator", "财务指标数据", "股票数据,财务数据", "获取上市公司财务指标数据", "/api/v1/ts/fina-indicator", "https://tushare.pro/wctapi/documents/79.md", 1, "stock_fina_indicator"),
    ("income", "利润表", "股票数据,财务数据", "获取上市公司财务利润表数据", "/api/v1/ts/income", "https://tushare.pro/wctapi/documents/33.md", 0, None),
    ("balancesheet", "资产负债表", "股票数据,财务数据", "获取上市公司资产负债表", "/api/v1/ts/balancesheet", "https://tushare.pro/wctapi/documents/36.md", 0, None),
    ("cashflow", "现金流量表", "股票数据,财务数据", "获取上市公司现金流量表", "/api/v1/ts/cashflow", "https://tushare.pro/wctapi/documents/44.md", 0, None),
    ("forecast", "业绩预告", "股票数据,财务数据", "获取业绩预告数据", "/api/v1/ts/forecast", "https://tushare.pro/wctapi/documents/45.md", 0, None),
    ("express", "业绩快报", "股票数据,财务数据", "获取上市公司业绩快报", "/api/v1/ts/express", "https://tushare.pro/wctapi/documents/46.md", 0, None),
    ("dividend", "分红送股数据", "股票数据,财务数据", "分红送股数据", "/api/v1/ts/dividend", "https://tushare.pro/wctapi/documents/103.md", 0, None),
    ("fina_mainbz", "主营业务构成", "股票数据,财务数据", "获得上市公司主营业务构成", "/api/v1/ts/fina-mainbz", "https://tushare.pro/wctapi/documents/81.md", 0, None),
    ("fina_audit", "财务审计意见", "股票数据,财务数据", "获取上市公司定期财务审计意见数据", "/api/v1/ts/fina-audit", "https://tushare.pro/wctapi/documents/80.md", 0, None),
    ("disclosure_date", "财报披露日期表", "股票数据,财务数据", "获取财报披露计划日期", "/api/v1/ts/disclosure-date", "https://tushare.pro/wctapi/documents/162.md", 0, None),
    # ====== 参考数据 ======
    ("top10_holders", "前十大股东", "股票数据,参考数据", "获取上市公司前十大股东数据", "/api/v1/ts/top10-holders", "https://tushare.pro/wctapi/documents/61.md", 0, None),
    ("top10_floatholders", "前十大流通股东", "股票数据,参考数据", "获取上市公司前十大流通股东数据", "/api/v1/ts/top10-floatholders", "https://tushare.pro/wctapi/documents/62.md", 0, None),
    ("stk_holdernumber", "股东人数", "股票数据,参考数据", "获取上市公司股东户数数据", "/api/v1/ts/stk-holdernumber", "https://tushare.pro/wctapi/documents/166.md", 0, None),
    ("stk_holdertrade", "股东增减持", "股票数据,参考数据", "获取上市公司增减持数据", "/api/v1/ts/stk-holdertrade", "https://tushare.pro/wctapi/documents/175.md", 0, None),
    ("pledge_stat", "股权质押统计", "股票数据,参考数据", "获取股票质押统计数据", "/api/v1/ts/pledge-stat", "https://tushare.pro/wctapi/documents/110.md", 0, None),
    ("pledge_detail", "股权质押明细", "股票数据,参考数据", "获取股票质押明细数据", "/api/v1/ts/pledge-detail", "https://tushare.pro/wctapi/documents/111.md", 0, None),
    ("repurchase", "股票回购", "股票数据,参考数据", "获取上市公司回购股票数据", "/api/v1/ts/repurchase", "https://tushare.pro/wctapi/documents/124.md", 0, None),
    ("share_float", "限售股解禁", "股票数据,参考数据", "获取限售股解禁", "/api/v1/ts/share-float", "https://tushare.pro/wctapi/documents/160.md", 0, None),
    ("block_trade", "大宗交易", "股票数据,参考数据", "大宗交易", "/api/v1/ts/block-trade", "https://tushare.pro/wctapi/documents/161.md", 0, None),
    ("new_share", "IPO新股上市", "股票数据,基础数据", "获取新股上市列表数据", "/api/v1/ts/new-share", "https://tushare.pro/wctapi/documents/123.md", 0, None),
    ("stock_company", "上市公司基本信息", "股票数据,基础数据", "获取上市公司基础信息", "/api/v1/ts/stock-company", "https://tushare.pro/wctapi/documents/112.md", 0, None),
    ("stk_managers", "上市公司管理层", "股票数据,基础数据", "获取上市公司管理层", "/api/v1/ts/stk-managers", "https://tushare.pro/wctapi/documents/193.md", 0, None),
    ("stk_rewards", "管理层薪酬和持股", "股票数据,基础数据", "获取上市公司管理层薪酬和持股", "/api/v1/ts/stk-rewards", "https://tushare.pro/wctapi/documents/194.md", 0, None),
    ("stock_hsgt", "沪深港通股票列表", "股票数据,基础数据", "获取沪深港通股票列表", "/api/v1/ts/stock-hsgt", "https://tushare.pro/wctapi/documents/398.md", 0, None),
    ("stock_st", "ST股票列表", "股票数据,基础数据", "获取ST股票列表", "/api/v1/ts/stock-st", "https://tushare.pro/wctapi/documents/397.md", 0, None),
    ("bak_basic", "股票历史列表", "股票数据,基础数据", "获取备用基础列表", "/api/v1/ts/bak-basic", "https://tushare.pro/wctapi/documents/262.md", 0, None),
    ("bse_mapping", "北交所新旧代码对照", "股票数据,基础数据", "获取北交所股票代码变更后新旧代码映射", "/api/v1/ts/bse-mapping", "https://tushare.pro/wctapi/documents/375.md", 0, None),
    ("st", "ST风险警示板股票", "股票数据,基础数据", "ST风险警示板股票列表", "/api/v1/ts/st", "https://tushare.pro/wctapi/documents/423.md", 0, None),
    ("stk_account", "股票开户数据", "股票数据,参考数据", "获取股票账户开户数据", "/api/v1/ts/stk-account", "https://tushare.pro/wctapi/documents/164.md", 0, None),
    ("stk_account_old", "股票开户数据(旧)", "股票数据,参考数据", "获取股票账户开户数据旧版格式", "/api/v1/ts/stk-account-old", "https://tushare.pro/wctapi/documents/165.md", 0, None),
    ("margin", "融资融券交易汇总", "股票数据,两融及转融通", "获取融资融券每日交易汇总数据", "/api/v1/ts/margin", "https://tushare.pro/wctapi/documents/58.md", 0, None),
    ("margin_detail", "融资融券交易明细", "股票数据,两融及转融通", "获取沪深两市每日融资融券明细", "/api/v1/ts/margin-detail", "https://tushare.pro/wctapi/documents/59.md", 0, None),
    ("margin_secs", "融资融券标的(盘前)", "股票数据,两融及转融通", "获取融资融券标的", "/api/v1/ts/margin-secs", "https://tushare.pro/wctapi/documents/326.md", 0, None),
    ("slb_len", "转融资交易汇总", "股票数据,两融及转融通", "转融通融资汇总", "/api/v1/ts/slb-len", "https://tushare.pro/wctapi/documents/331.md", 0, None),
    ("slb_sec", "转融券交易汇总", "股票数据,两融及转融通", "转融通转融券交易汇总", "/api/v1/ts/slb-sec", "https://tushare.pro/wctapi/documents/332.md", 0, None),
    ("slb_sec_detail", "转融券交易明细", "股票数据,两融及转融通", "转融券交易明细", "/api/v1/ts/slb-sec-detail", "https://tushare.pro/wctapi/documents/333.md", 0, None),
    ("slb_len_mm", "做市借券交易汇总", "股票数据,两融及转融通", "做市借券交易汇总", "/api/v1/ts/slb-len-mm", "https://tushare.pro/wctapi/documents/334.md", 0, None),
    # ====== 打板/题材/龙虎榜 ======
    ("top_list", "龙虎榜每日统计单", "股票数据,打板专题数据", "龙虎榜每日交易明细", "/api/v1/ts/top-list", "https://tushare.pro/wctapi/documents/106.md", 1, "top_list"),
    ("top_inst", "龙虎榜机构交易单", "股票数据,打板专题数据", "龙虎榜机构成交明细", "/api/v1/ts/top-inst", "https://tushare.pro/wctapi/documents/107.md", 1, "top_inst"),
    ("limit_list_d", "涨跌停和炸板数据", "股票数据,打板专题数据", "获取A股每日涨跌停、炸板数据", "/api/v1/ts/limit-list-d", "https://tushare.pro/wctapi/documents/298.md", 0, None),
    ("limit_step", "涨停股票连板天梯", "股票数据,打板专题数据", "获取每天连板个数晋级的股票", "/api/v1/ts/limit-step", "https://tushare.pro/wctapi/documents/356.md", 0, None),
    ("limit_cpt_list", "涨停最强板块统计", "股票数据,打板专题数据", "获取每天涨停股票最多最强的概念板块", "/api/v1/ts/limit-cpt-list", "https://tushare.pro/wctapi/documents/357.md", 0, None),
    ("limit_list_ths", "THS涨跌停榜单", "股票数据,打板专题数据", "获取同花顺每日涨跌停榜单数据", "/api/v1/ts/limit-list-ths", "https://tushare.pro/wctapi/documents/355.md", 0, None),
    ("kpl_list", "榜单数据(KP)", "股票数据,打板专题数据", "获取涨停、跌停、炸板等榜单数据", "/api/v1/ts/kpl-list", "https://tushare.pro/wctapi/documents/347.md", 0, None),
    ("kpl_concept_cons", "题材成分(KP)", "股票数据,打板专题数据", "获取概念题材的成分股", "/api/v1/ts/kpl-concept-cons", "https://tushare.pro/wctapi/documents/351.md", 0, None),
    ("ths_index", "THS概念板块分类", "股票数据,打板专题数据", "获取板块指数列表", "/api/v1/ts/ths-index", "https://tushare.pro/wctapi/documents/259.md", 1, "ths_index"),
    ("ths_daily", "THS概念板块行情", "股票数据,打板专题数据", "获取板块指数行情", "/api/v1/ts/ths-daily", "https://tushare.pro/wctapi/documents/260.md", 1, "ths_daily"),
    ("ths_member", "THS概念板块成分", "股票数据,打板专题数据", "获取概念板块成分列表", "/api/v1/ts/ths-member", "https://tushare.pro/wctapi/documents/261.md", 1, "ths_member"),
    ("ths_hot", "THS热榜", "股票数据,打板专题数据", "获取热榜数据", "/api/v1/ts/ths-hot", "https://tushare.pro/wctapi/documents/320.md", 0, None),
    ("dc_index", "DC概念板块分类", "股票数据,打板专题数据", "获取每个交易日的概念板块数据", "/api/v1/ts/dc-index", "https://tushare.pro/wctapi/documents/362.md", 0, None),
    ("dc_member", "DC概念板块成分", "股票数据,打板专题数据", "获取板块每日成分数据", "/api/v1/ts/dc-member", "https://tushare.pro/wctapi/documents/363.md", 0, None),
    ("dc_daily", "DC概念板块行情", "股票数据,打板专题数据", "获取概念板块行情数据", "/api/v1/ts/dc-daily", "https://tushare.pro/wctapi/documents/382.md", 0, None),
    ("dc_hot", "DC热榜", "股票数据,打板专题数据", "获取热榜数据", "/api/v1/ts/dc-hot", "https://tushare.pro/wctapi/documents/321.md", 0, None),
    ("dc_concept", "题材数据(DC)", "股票数据,打板专题数据", "获取概念题材列表", "/api/v1/ts/dc-concept", "https://tushare.pro/wctapi/documents/421.md", 0, None),
    ("dc_concept_cons", "题材成分(DC)", "股票数据,打板专题数据", "获取概念题材的成分股", "/api/v1/ts/dc-concept-cons", "https://tushare.pro/wctapi/documents/422.md", 0, None),
    ("tdx_index", "TDX概念板块分类", "股票数据,打板专题数据", "获取板块基础信息", "/api/v1/ts/tdx-index", "https://tushare.pro/wctapi/documents/376.md", 0, None),
    ("tdx_member", "TDX概念板块成分", "股票数据,打板专题数据", "获取各板块成分股信息", "/api/v1/ts/tdx-member", "https://tushare.pro/wctapi/documents/377.md", 0, None),
    ("tdx_daily", "TDX概念板块行情", "股票数据,打板专题数据", "获取各板块行情", "/api/v1/ts/tdx-daily", "https://tushare.pro/wctapi/documents/378.md", 0, None),
    ("hm_list", "市场游资名录", "股票数据,打板专题数据", "获取游资分类名录信息", "/api/v1/ts/hm-list", "https://tushare.pro/wctapi/documents/311.md", 0, None),
    ("hm_detail", "游资交易每日明细", "股票数据,打板专题数据", "获取每日游资交易明细", "/api/v1/ts/hm-detail", "https://tushare.pro/wctapi/documents/312.md", 0, None),
    ("stk_auction", "开盘竞价成交(当日)", "股票数据,打板专题数据", "获取当日个股和ETF的集合竞价成交情况", "/api/v1/ts/stk-auction", "https://tushare.pro/wctapi/documents/369.md", 0, None),
    ("stk_auction_o", "股票开盘集合竞价数据", "股票数据,特色数据", "股票开盘9:30集合竞价数据", "/api/v1/ts/stk-auction-o", "https://tushare.pro/wctapi/documents/353.md", 0, None),
    ("stk_auction_c", "股票收盘集合竞价数据", "股票数据,特色数据", "股票收盘15:00集合竞价数据", "/api/v1/ts/stk-auction-c", "https://tushare.pro/wctapi/documents/354.md", 0, None),
    ("broker_recommend", "券商月度金股", "股票数据,特色数据", "获取券商月度金股", "/api/v1/ts/broker-recommend", "https://tushare.pro/wctapi/documents/267.md", 0, None),
    # ====== 资金流向 ======
    ("moneyflow", "个股资金流向", "股票数据,资金流向数据", "获取沪深A股票资金流向数据", "/api/v1/ts/moneyflow", "https://tushare.pro/wctapi/documents/170.md", 1, "stock_moneyflow"),
    ("moneyflow_hsgt", "沪深港通资金流向", "股票数据,资金流向数据", "获取沪股通、深股通、港股通每日资金流向数据", "/api/v1/ts/moneyflow-hsgt", "https://tushare.pro/wctapi/documents/47.md", 1, "moneyflow_hsgt"),
    ("moneyflow_cnt_ths", "板块资金流向(THS)", "股票数据,资金流向数据", "获取同花顺概念板块每日资金流向", "/api/v1/ts/moneyflow-cnt-ths", "https://tushare.pro/wctapi/documents/371.md", 0, None),
    ("moneyflow_ind_ths", "行业资金流向(THS)", "股票数据,资金流向数据", "获取同花顺行业资金流向", "/api/v1/ts/moneyflow-ind-ths", "https://tushare.pro/wctapi/documents/343.md", 1, "sector_moneyflow_industry"),
    ("moneyflow_ind_dc", "板块资金流向(DC)", "股票数据,资金流向数据", "获取东方财富板块资金流向", "/api/v1/ts/moneyflow-ind-dc", "https://tushare.pro/wctapi/documents/344.md", 0, None),
    ("moneyflow_mkt_dc", "大盘资金流向(DC)", "股票数据,资金流向数据", "获取东方财富大盘资金流向数据", "/api/v1/ts/moneyflow-mkt-dc", "https://tushare.pro/wctapi/documents/345.md", 0, None),
    ("moneyflow_ths", "个股资金流向(THS)", "股票数据,资金流向数据", "获取同花顺个股资金流向数据", "/api/v1/ts/moneyflow-ths", "https://tushare.pro/wctapi/documents/348.md", 0, None),
    ("moneyflow_dc", "个股资金流向(DC)", "股票数据,资金流向数据", "获取东方财富个股资金流向数据", "/api/v1/ts/moneyflow-dc", "https://tushare.pro/wctapi/documents/349.md", 0, None),
    # ====== 特色数据 ======
    ("cyq_perf", "每日筹码及胜率", "股票数据,特色数据", "获取A股每日筹码平均成本和胜率情况", "/api/v1/ts/cyq-perf", "https://tushare.pro/wctapi/documents/293.md", 0, None),
    ("cyq_chips", "每日筹码分布", "股票数据,特色数据", "获取A股每日的筹码分布情况", "/api/v1/ts/cyq-chips", "https://tushare.pro/wctapi/documents/294.md", 0, None),
    ("stk_factor", "股票技术面因子", "股票数据,特色数据", "获取股票每日技术面因子数据", "/api/v1/ts/stk-factor", "https://tushare.pro/wctapi/documents/296.md", 0, None),
    ("stk_factor_pro", "股票技术面因子(专业版)", "股票数据,特色数据", "获取股票每日技术面因子数据(专业版)", "/api/v1/ts/stk-factor-pro", "https://tushare.pro/wctapi/documents/328.md", 0, None),
    ("stk_nineturn", "神奇九转指标", "股票数据,特色数据", "神奇九转趋势反转指标", "/api/v1/ts/stk-nineturn", "https://tushare.pro/wctapi/documents/364.md", 0, None),
    ("hk_hold", "沪深股通持股明细", "股票数据,特色数据", "获取沪深港股通持股明细", "/api/v1/ts/hk-hold", "https://tushare.pro/wctapi/documents/188.md", 0, None),
    ("stk_surv", "机构调研数据", "股票数据,特色数据", "获取上市公司机构调研记录数据", "/api/v1/ts/stk-surv", "https://tushare.pro/wctapi/documents/275.md", 0, None),
    ("report_rc", "券商盈利预测数据", "股票数据,特色数据", "获取券商每天研报的盈利预测数据", "/api/v1/ts/report-rc", "https://tushare.pro/wctapi/documents/292.md", 0, None),
    ("stk_alert", "交易所重点提示证券", "股票数据,参考数据", "交易所每日发布重点提示证券", "/api/v1/ts/stk-alert", "https://tushare.pro/wctapi/documents/453.md", 0, None),
    ("stk_shock", "个股异常波动", "股票数据,参考数据", "交易所每日发布股票交易异常波动情况", "/api/v1/ts/stk-shock", "https://tushare.pro/wctapi/documents/451.md", 0, None),
    ("stk_high_shock", "个股严重异常波动", "股票数据,参考数据", "交易所每日发布股票交易严重异常波动", "/api/v1/ts/stk-high-shock", "https://tushare.pro/wctapi/documents/452.md", 0, None),
    ("ccass_hold", "中央结算系统持股统计", "股票数据,特色数据", "获取中央结算系统持股汇总数据", "/api/v1/ts/ccass-hold", "https://tushare.pro/wctapi/documents/295.md", 0, None),
    ("ccass_hold_detail", "中央结算系统持股明细", "股票数据,特色数据", "获取中央结算系统机构席位持股明细", "/api/v1/ts/ccass-hold-detail", "https://tushare.pro/wctapi/documents/274.md", 0, None),
    ("stk_ah_comparison", "AH股比价", "股票数据,特色数据", "AH股比价数据", "/api/v1/ts/stk-ah-comparison", "https://tushare.pro/wctapi/documents/399.md", 0, None),
    # ====== 公募基金 ======
    ("fund_basic", "基金列表", "公募基金", "获取公募基金数据列表", "/api/v1/ts/fund-basic", "https://tushare.pro/wctapi/documents/19.md", 0, None),
    ("fund_nav", "基金净值", "公募基金", "获取公募基金净值数据", "/api/v1/ts/fund-nav", "https://tushare.pro/wctapi/documents/119.md", 0, None),
    ("fund_share", "基金规模", "公募基金", "获取基金规模数据", "/api/v1/ts/fund-share", "https://tushare.pro/wctapi/documents/207.md", 0, None),
    ("fund_portfolio", "基金持仓", "公募基金", "获取公募基金持仓数据", "/api/v1/ts/fund-portfolio", "https://tushare.pro/wctapi/documents/121.md", 0, None),
    ("fund_div", "基金分红", "公募基金", "获取公募基金分红数据", "/api/v1/ts/fund-div", "https://tushare.pro/wctapi/documents/120.md", 0, None),
    ("fund_manager", "基金经理", "公募基金", "获取公募基金经理数据", "/api/v1/ts/fund-manager", "https://tushare.pro/wctapi/documents/208.md", 0, None),
    ("fund_company", "基金管理人", "公募基金", "获取公募基金管理人列表", "/api/v1/ts/fund-company", "https://tushare.pro/wctapi/documents/118.md", 0, None),
    ("fund_factor_pro", "基金技术面因子(专业版)", "公募基金", "获取场内基金每日技术面因子数据", "/api/v1/ts/fund-factor-pro", "https://tushare.pro/wctapi/documents/359.md", 0, None),
    ("mkt_idx_bmk", "基金业绩基准", "公募基金", "获取ETF业绩比较基准列表信息", "/api/v1/ts/mkt-idx-bmk", "https://tushare.pro/wctapi/documents/462.md", 0, None),
    # ====== 指数 ======
    ("index_basic", "指数基本信息", "指数专题", "获取指数基础信息", "/api/v1/ts/index-basic", "https://tushare.pro/wctapi/documents/94.md", 1, "index_basic"),
    ("index_daily", "指数日线行情", "指数专题", "获取指数每日行情", "/api/v1/ts/index-daily", "https://tushare.pro/wctapi/documents/95.md", 1, "index_daily"),
    ("index_weekly", "指数周线行情", "指数专题", "获取指数周线行情", "/api/v1/ts/index-weekly", "https://tushare.pro/wctapi/documents/171.md", 0, None),
    ("index_monthly", "指数月线行情", "指数专题", "获取指数月线行情", "/api/v1/ts/index-monthly", "https://tushare.pro/wctapi/documents/172.md", 0, None),
    ("index_weight", "指数成分和权重", "指数专题", "获取各类指数成分和权重", "/api/v1/ts/index-weight", "https://tushare.pro/wctapi/documents/96.md", 0, None),
    ("index_dailybasic", "大盘指数每日指标", "指数专题", "提供主要指数的每日指标数据", "/api/v1/ts/index-dailybasic", "https://tushare.pro/wctapi/documents/128.md", 0, None),
    ("index_classify", "申万行业分类", "指数专题", "获取申万行业分类", "/api/v1/ts/index-classify", "https://tushare.pro/wctapi/documents/181.md", 0, None),
    ("index_member_all", "申万行业成分(分级)", "指数专题", "按三级分类提取申万行业成分", "/api/v1/ts/index-member-all", "https://tushare.pro/wctapi/documents/335.md", 0, None),
    ("index_global", "国际主要指数", "指数专题", "获取国际主要指数日线行情", "/api/v1/ts/index-global", "https://tushare.pro/wctapi/documents/211.md", 0, None),
    ("sw_daily", "申万日线行情", "指数专题", "获取申万行业日线行情", "/api/v1/ts/sw-daily", "https://tushare.pro/wctapi/documents/327.md", 0, None),
    ("sw_mins", "SW历史分钟", "指数专题", "获取申万指数历史分钟数据", "/api/v1/ts/sw-mins", "https://tushare.pro/wctapi/documents/469.md", 0, None),
    ("rt_sw_k", "申万实时行情", "指数专题", "获取申万行业指数的最新截面数据", "/api/v1/ts/rt-sw-k", "https://tushare.pro/wctapi/documents/417.md", 0, None),
    ("rt_idx_k", "指数实时日线", "指数专题", "获取交易所指数实时日线行情", "/api/v1/ts/rt-idx-k", "https://tushare.pro/wctapi/documents/403.md", 0, None),
    ("rt_idx_min", "指数实时分钟", "指数专题", "获取交易所指数实时分钟数据", "/api/v1/ts/rt-idx-min", "https://tushare.pro/wctapi/documents/420.md", 0, None),
    ("idx_mins", "指数历史分钟", "指数专题", "获取交易所指数分钟数据", "/api/v1/ts/idx-mins", "https://tushare.pro/wctapi/documents/419.md", 0, None),
    ("idx_factor_pro", "指数技术面因子(专业版)", "指数专题", "获取指数每日技术面因子数据", "/api/v1/ts/idx-factor-pro", "https://tushare.pro/wctapi/documents/358.md", 0, None),
    ("ci_daily", "中信行业指数日行情", "指数专题", "获取中信行业指数日线行情", "/api/v1/ts/ci-daily", "https://tushare.pro/wctapi/documents/308.md", 0, None),
    ("ci_index_member", "中信行业成分", "指数专题", "按三级分类提取中信行业成分", "/api/v1/ts/ci-index-member", "https://tushare.pro/wctapi/documents/373.md", 0, None),
    ("daily_info", "沪深市场每日交易统计", "指数专题", "获取交易所股票交易统计", "/api/v1/ts/daily-info", "https://tushare.pro/wctapi/documents/215.md", 0, None),
    ("sz_daily_info", "深圳市场每日交易情况", "指数专题", "获取深圳市场每日交易概况", "/api/v1/ts/sz-daily-info", "https://tushare.pro/wctapi/documents/268.md", 0, None),
    # ====== 宏观/新闻/语料 ======
    ("news", "新闻快讯(短讯)", "大模型语料", "获取主流新闻网站的快讯新闻数据", "/api/v1/ts/news", "https://tushare.pro/wctapi/documents/143.md", 0, None),
    ("major_news", "新闻通讯(长篇)", "大模型语料", "获取长篇通讯信息", "/api/v1/ts/major-news", "https://tushare.pro/wctapi/documents/195.md", 0, None),
    ("cctv_news", "新闻联播文字稿", "大模型语料", "获取新闻联播文字稿数据", "/api/v1/ts/cctv-news", "https://tushare.pro/wctapi/documents/154.md", 0, None),
    ("irm_qa_sh", "上证e互动问答", "大模型语料", "获取上交所e互动董秘问答文本数据", "/api/v1/ts/irm-qa-sh", "https://tushare.pro/wctapi/documents/366.md", 0, None),
    ("irm_qa_sz", "深证易互动问答", "大模型语料", "获取深交所互动易问答数据", "/api/v1/ts/irm-qa-sz", "https://tushare.pro/wctapi/documents/367.md", 0, None),
    ("npr", "国家政策库", "大模型语料", "获取国家行政机关公开披露的法规政策文本", "/api/v1/ts/npr", "https://tushare.pro/wctapi/documents/406.md", 0, None),
    ("monetary_policy", "央行货币政策执行报告", "大模型语料", "获取央行季度货币政策执行报告", "/api/v1/ts/monetary-policy", "https://tushare.pro/wctapi/documents/465.md", 0, None),
    ("research_report", "券商研究报告", "大模型语料", "获取券商研究报告", "/api/v1/ts/research-report", "https://tushare.pro/wctapi/documents/415.md", 0, None),
    ("anns_d", "上市公司公告", "大模型语料", "获取全量公告数据", "/api/v1/ts/anns-d", "https://tushare.pro/wctapi/documents/176.md", 0, None),
    ("shibor", "Shibor利率", "宏观经济,利率数据", "shibor利率", "/api/v1/ts/shibor", "https://tushare.pro/wctapi/documents/149.md", 0, None),
    ("shibor_quote", "Shibor报价数据", "宏观经济,利率数据", "Shibor报价数据", "/api/v1/ts/shibor-quote", "https://tushare.pro/wctapi/documents/150.md", 0, None),
    ("shibor_lpr", "LPR贷款基础利率", "宏观经济,利率数据", "LPR贷款基础利率", "/api/v1/ts/shibor-lpr", "https://tushare.pro/wctapi/documents/151.md", 0, None),
    ("libor", "Libor利率", "宏观经济,利率数据", "Libor拆借利率", "/api/v1/ts/libor", "https://tushare.pro/wctapi/documents/152.md", 0, None),
    ("hibor", "Hibor利率", "宏观经济,利率数据", "Hibor利率", "/api/v1/ts/hibor", "https://tushare.pro/wctapi/documents/153.md", 0, None),
    ("gz_index", "广州民间借贷利率", "宏观经济,利率数据", "广州民间借贷利率", "/api/v1/ts/gz-index", "https://tushare.pro/wctapi/documents/174.md", 0, None),
    ("wz_index", "温州民间借贷利率", "宏观经济,利率数据", "温州民间借贷利率", "/api/v1/ts/wz-index", "https://tushare.pro/wctapi/documents/173.md", 0, None),
    ("cn_cpi", "居民消费价格指数(CPI)", "宏观经济,价格指数", "获取CPI居民消费价格数据", "/api/v1/ts/cn-cpi", "https://tushare.pro/wctapi/documents/228.md", 0, None),
    ("cn_ppi", "工业生产者出厂价格指数(PPI)", "宏观经济,价格指数", "获取PPI数据", "/api/v1/ts/cn-ppi", "https://tushare.pro/wctapi/documents/245.md", 0, None),
    ("cn_gdp", "国内生产总值(GDP)", "宏观经济,国民经济", "获取国民经济之GDP数据", "/api/v1/ts/cn-gdp", "https://tushare.pro/wctapi/documents/227.md", 0, None),
    ("cn_m", "货币供应量(月)", "宏观经济,货币供应量", "获取货币供应量之月度数据", "/api/v1/ts/cn-m", "https://tushare.pro/wctapi/documents/242.md", 0, None),
    ("cn_pmi", "采购经理指数(PMI)", "宏观经济,景气度", "采购经理人指数", "/api/v1/ts/cn-pmi", "https://tushare.pro/wctapi/documents/325.md", 0, None),
    ("cn_schedule", "中国经济数据发布日程", "宏观经济", "获取经济数据发布日程", "/api/v1/ts/cn-schedule", "https://tushare.pro/wctapi/documents/461.md", 0, None),
    ("sf_month", "社融增量(月度)", "宏观经济,社会融资", "获取月度社会融资数据", "/api/v1/ts/sf-month", "https://tushare.pro/wctapi/documents/310.md", 0, None),
    ("eco_cal", "全球财经事件", "宏观经济", "获取全球财经日历", "/api/v1/ts/eco-cal", "https://tushare.pro/wctapi/documents/233.md", 0, None),
    ("us_tycr", "美国国债收益率曲线利率", "宏观经济,美国利率", "获取美国每日国债收益率曲线利率", "/api/v1/ts/us-tycr", "https://tushare.pro/wctapi/documents/219.md", 0, None),
    ("us_trltr", "国债长期利率平均值", "宏观经济,美国利率", "国债实际长期利率平均值", "/api/v1/ts/us-trltr", "https://tushare.pro/wctapi/documents/223.md", 0, None),
    ("us_trycr", "国债实际收益率曲线利率", "宏观经济,美国利率", "国债实际收益率曲线利率", "/api/v1/ts/us-trycr", "https://tushare.pro/wctapi/documents/220.md", 0, None),
    ("us_tbr", "短期国债利率", "宏观经济,美国利率", "获取美国短期国债利率数据", "/api/v1/ts/us-tbr", "https://tushare.pro/wctapi/documents/221.md", 0, None),
    ("us_tltr", "国债长期利率", "宏观经济,美国利率", "国债长期利率", "/api/v1/ts/us-tltr", "https://tushare.pro/wctapi/documents/222.md", 0, None),
    # ====== 债券/可转债 ======
    ("cb_basic", "可转债基础信息", "债券专题", "获取可转债基本信息", "/api/v1/ts/cb-basic", "https://tushare.pro/wctapi/documents/185.md", 0, None),
    ("cb_issue", "可转债发行", "债券专题", "获取可转债发行数据", "/api/v1/ts/cb-issue", "https://tushare.pro/wctapi/documents/186.md", 0, None),
    ("cb_daily", "可转债行情", "债券专题", "获取可转债行情", "/api/v1/ts/cb-daily", "https://tushare.pro/wctapi/documents/187.md", 0, None),
    ("cb_factor_pro", "可转债技术面因子(专业版)", "债券专题", "获取可转债每日技术面因子数据", "/api/v1/ts/cb-factor-pro", "https://tushare.pro/wctapi/documents/392.md", 0, None),
    ("cb_rating", "可转债债券评级", "债券专题", "获取可转债评级历史记录", "/api/v1/ts/cb-rating", "https://tushare.pro/wctapi/documents/458.md", 0, None),
    ("cb_call", "可转债赎回信息", "债券专题", "获取可转债赎回信息", "/api/v1/ts/cb-call", "https://tushare.pro/wctapi/documents/269.md", 0, None),
    ("cb_share", "可转债转股结果", "债券专题", "获取可转债转股结果", "/api/v1/ts/cb-share", "https://tushare.pro/wctapi/documents/247.md", 0, None),
    ("cb_price_chg", "可转债转股价变动", "债券专题", "获取可转债转股价变动", "/api/v1/ts/cb-price-chg", "https://tushare.pro/wctapi/documents/246.md", 0, None),
    ("cb_rate", "可转债票面利率", "债券专题", "获取可转债票面利率", "/api/v1/ts/cb-rate", "https://tushare.pro/wctapi/documents/305.md", 0, None),
    ("top10_cb_holders", "可转债十大持有人", "债券专题", "获取可转债前十大持有人", "/api/v1/ts/top10-cb-holders", "https://tushare.pro/wctapi/documents/459.md", 0, None),
    ("yc_cb", "国债收益率曲线", "债券专题", "获取中债收益率曲线", "/api/v1/ts/yc-cb", "https://tushare.pro/wctapi/documents/201.md", 0, None),
    ("repo_daily", "债券回购日行情", "债券专题", "债券回购日行情", "/api/v1/ts/repo-daily", "https://tushare.pro/wctapi/documents/256.md", 0, None),
    ("bond_blk", "大宗交易(债券)", "债券专题", "获取沪深交易所债券大宗交易数据", "/api/v1/ts/bond-blk", "https://tushare.pro/wctapi/documents/271.md", 0, None),
    ("bond_blk_detail", "大宗交易明细(债券)", "债券专题", "获取债券大宗交易明细", "/api/v1/ts/bond-blk-detail", "https://tushare.pro/wctapi/documents/272.md", 0, None),
    ("bc_otcqt", "柜台流通式债券报价", "债券专题", "柜台流通式债券报价", "/api/v1/ts/bc-otcqt", "https://tushare.pro/wctapi/documents/322.md", 0, None),
    ("bc_bestotcqt", "柜台流通式债券最优报价", "债券专题", "柜台流通式债券最优报价", "/api/v1/ts/bc-bestotcqt", "https://tushare.pro/wctapi/documents/323.md", 0, None),
    # ====== 外汇 ======
    ("fx_obasic", "外汇基础信息(海外)", "外汇数据", "获取海外外汇基础信息", "/api/v1/ts/fx-obasic", "https://tushare.pro/wctapi/documents/178.md", 0, None),
    ("fx_daily", "外汇日线行情", "外汇数据", "获取外汇日线行情", "/api/v1/ts/fx-daily", "https://tushare.pro/wctapi/documents/179.md", 0, None),
    # ====== 期权 ======
    ("opt_basic", "期权合约信息", "期权数据", "获取期权合约信息", "/api/v1/ts/opt-basic", "https://tushare.pro/wctapi/documents/158.md", 0, None),
    ("opt_daily", "期权日线行情", "期权数据", "获取期权日线行情", "/api/v1/ts/opt-daily", "https://tushare.pro/wctapi/documents/159.md", 0, None),
    ("opt_mins", "期权分钟行情", "期权数据", "获取期权合约分钟数据", "/api/v1/ts/opt-mins", "https://tushare.pro/wctapi/documents/341.md", 0, None),
    # ====== 期货 ======
    ("fut_basic", "合约信息", "期货数据", "获取期货合约列表数据", "/api/v1/ts/fut-basic", "https://tushare.pro/wctapi/documents/135.md", 0, None),
    ("fut_daily", "日线行情", "期货数据", "期货日线行情数据", "/api/v1/ts/fut-daily", "https://tushare.pro/wctapi/documents/138.md", 0, None),
    ("fut_holding", "每日持仓排名", "期货数据", "获取每日成交持仓排名数据", "/api/v1/ts/fut-holding", "https://tushare.pro/wctapi/documents/139.md", 0, None),
    ("fut_wsr", "仓单日报", "期货数据", "获取仓单日报数据", "/api/v1/ts/fut-wsr", "https://tushare.pro/wctapi/documents/140.md", 0, None),
    ("fut_settle", "每日结算参数", "期货数据", "获取每日结算参数数据", "/api/v1/ts/fut-settle", "https://tushare.pro/wctapi/documents/141.md", 0, None),
    ("fut_weekly_detail", "期货主要品种交易周报", "期货数据", "获取期货交易所主要品种每周交易统计", "/api/v1/ts/fut-weekly-detail", "https://tushare.pro/wctapi/documents/216.md", 0, None),
    ("fut_weekly_monthly", "期货周月线行情", "期货数据", "期货周/月线行情(每日更新)", "/api/v1/ts/fut-weekly-monthly", "https://tushare.pro/wctapi/documents/337.md", 0, None),
    ("fut_mapping", "期货主力与连续合约", "期货数据", "获取期货主力合约与月合约映射数据", "/api/v1/ts/fut-mapping", "https://tushare.pro/wctapi/documents/189.md", 0, None),
    ("fut_trade_cal", "期货交易日历", "期货数据", "获取各大期货交易所交易日历数据", "/api/v1/ts/fut-trade-cal", "https://tushare.pro/wctapi/documents/467.md", 0, None),
    ("fut_index_daily", "南华期货指数日线行情", "期货数据", "获取南华指数每日行情", "/api/v1/ts/fut-index-daily", "https://tushare.pro/wctapi/documents/468.md", 0, None),
    ("ft_mins", "历史分钟行情", "期货数据", "获取期货合约分钟数据", "/api/v1/ts/ft-mins", "https://tushare.pro/wctapi/documents/313.md", 0, None),
    ("ft_limit", "期货合约涨跌停价格", "期货数据", "获取期货合约每天的涨跌停价格", "/api/v1/ts/ft-limit", "https://tushare.pro/wctapi/documents/368.md", 0, None),
    ("rt_fut_min", "实时分钟行情", "期货数据", "获取期货合约实时分钟数据", "/api/v1/ts/rt-fut-min", "https://tushare.pro/wctapi/documents/340.md", 0, None),
    # ====== 港股 ======
    ("hk_basic", "港股基础信息", "港股数据", "获取港股列表信息", "/api/v1/ts/hk-basic", "https://tushare.pro/wctapi/documents/191.md", 0, None),
    ("hk_tradecal", "港股交易日历", "港股数据", "获取港股交易日历", "/api/v1/ts/hk-tradecal", "https://tushare.pro/wctapi/documents/250.md", 0, None),
    ("hk_daily", "港股日线行情", "港股数据", "获取港股每日行情", "/api/v1/ts/hk-daily", "https://tushare.pro/wctapi/documents/192.md", 0, None),
    ("hk_daily_adj", "港股复权行情", "港股数据", "获取港股复权行情", "/api/v1/ts/hk-daily-adj", "https://tushare.pro/wctapi/documents/339.md", 0, None),
    ("hk_adjfactor", "港股复权因子", "港股数据", "获取港股每日复权因子数据", "/api/v1/ts/hk-adjfactor", "https://tushare.pro/wctapi/documents/401.md", 0, None),
    ("hk_mins", "港股分钟行情", "港股数据", "港股分钟数据", "/api/v1/ts/hk-mins", "https://tushare.pro/wctapi/documents/304.md", 0, None),
    ("hk_fina_indicator", "港股财务指标数据", "港股数据", "获取港股上市公司财务指标数据", "/api/v1/ts/hk-fina-indicator", "https://tushare.pro/wctapi/documents/388.md", 0, None),
    ("hk_income", "港股利润表", "港股数据", "获取港股上市公司财务利润表数据", "/api/v1/ts/hk-income", "https://tushare.pro/wctapi/documents/389.md", 0, None),
    ("hk_balancesheet", "港股资产负债表", "港股数据", "获取港股上市公司资产负债表", "/api/v1/ts/hk-balancesheet", "https://tushare.pro/wctapi/documents/390.md", 0, None),
    ("hk_cashflow", "港股现金流量表", "港股数据", "获取港股上市公司现金流量表数据", "/api/v1/ts/hk-cashflow", "https://tushare.pro/wctapi/documents/391.md", 0, None),
    ("rt_hk_k", "港股实时日线", "港股数据", "获取港股实时日k线行情", "/api/v1/ts/rt-hk-k", "https://tushare.pro/wctapi/documents/383.md", 0, None),
    # ====== 美股 ======
    ("us_basic", "美股基础信息", "美股数据", "获取美股列表信息", "/api/v1/ts/us-basic", "https://tushare.pro/wctapi/documents/252.md", 0, None),
    ("us_tradecal", "美股交易日历", "美股数据", "获取美股交易日历信息", "/api/v1/ts/us-tradecal", "https://tushare.pro/wctapi/documents/253.md", 0, None),
    ("us_daily", "美股日线行情", "美股数据", "获取美股行情（未复权）", "/api/v1/ts/us-daily", "https://tushare.pro/wctapi/documents/254.md", 0, None),
    ("us_daily_adj", "美股复权行情", "美股数据", "获取美股复权行情", "/api/v1/ts/us-daily-adj", "https://tushare.pro/wctapi/documents/338.md", 0, None),
    ("us_adjfactor", "美股复权因子", "美股数据", "获取美股每日复权因子数据", "/api/v1/ts/us-adjfactor", "https://tushare.pro/wctapi/documents/402.md", 0, None),
    ("us_fina_indicator", "美股财务指标数据", "美股数据", "获取美股上市公司财务指标数据", "/api/v1/ts/us-fina-indicator", "https://tushare.pro/wctapi/documents/393.md", 0, None),
    ("us_income", "美股利润表", "美股数据", "获取美股上市公司财务利润表数据", "/api/v1/ts/us-income", "https://tushare.pro/wctapi/documents/394.md", 0, None),
    ("us_balancesheet", "美股资产负债表", "美股数据", "获取美股上市公司资产负债表", "/api/v1/ts/us-balancesheet", "https://tushare.pro/wctapi/documents/395.md", 0, None),
    ("us_cashflow", "美股现金流量表", "美股数据", "获取美股上市公司现金流量表数据", "/api/v1/ts/us-cashflow", "https://tushare.pro/wctapi/documents/396.md", 0, None),
    # ====== 现货 ======
    ("sge_basic", "上海黄金基础信息", "现货数据", "获取上海黄金交易所现货合约基础信息", "/api/v1/ts/sge-basic", "https://tushare.pro/wctapi/documents/284.md", 0, None),
    ("sge_daily", "上海黄金现货日行情", "现货数据", "获取上海黄金交易所现货合约日线行情", "/api/v1/ts/sge-daily", "https://tushare.pro/wctapi/documents/285.md", 0, None),
    # ====== 自选组合 ======
    ("p_save", "组合保存", "自选组合", "创建或修改自选股组合", "/api/v1/ts/p-save", "https://tushare.pro/wctapi/documents/445.md", 0, None),
    ("p_list", "组合列表", "自选组合", "自选股组合查询", "/api/v1/ts/p-list", "https://tushare.pro/wctapi/documents/446.md", 0, None),
    ("p_delete", "组合删除", "自选组合", "删除自选股组合", "/api/v1/ts/p-delete", "https://tushare.pro/wctapi/documents/447.md", 0, None),
    ("p_get", "成分查询", "自选组合", "查询组合的成分列表", "/api/v1/ts/p-get", "https://tushare.pro/wctapi/documents/449.md", 0, None),
]


# ============================================================
# AKShare 数据源种子
# 格式同 Tushare: (api_name, title, category, description, proxy_path, doc_url, has_local_table, local_table_name)
# ============================================================

_AKSHARE_SEED_DATA = [
    # ====== A股实时行情 ======
    ("stock_zh_a_minute", "A股分钟K线", "A股行情,分时数据", "获取A股分钟级别K线数据", "/api/v1/ak/stock-zh-a-minute", "https://akshare.akfamily.xyz/data/stock/stock.html#id4", 0, None),
    ("stock_zh_a_hist", "A股历史行情", "A股行情,日线数据", "获取A股个股历史行情数据（前后复权）", "/api/v1/ak/stock-zh-a-hist", "https://akshare.akfamily.xyz/data/stock/stock.html#id1", 0, None),
    ("stock_zh_a_spot_em", "A股实时行情(东财)", "A股行情,实时数据", "获取东方财富A股实时行情数据", "/api/v1/ak/stock-zh-a-spot-em", "https://akshare.akfamily.xyz/data/stock/stock.html#id7", 0, None),
    ("stock_zh_a_hist_min_em", "A股分时行情(东财)", "A股行情,分时数据", "获取东方财富A股分时行情数据", "/api/v1/ak/stock-zh-a-hist-min-em", "https://akshare.akfamily.xyz/data/stock/stock.html#id8", 0, None),
    # ====== 板块/概念 ======
    ("stock_board_industry_name_em", "行业板块列表(东财)", "板块数据,行业板块", "获取东方财富行业板块名称列表", "/api/v1/ak/stock-board-industry-name-em", "https://akshare.akfamily.xyz/data/stock/stock.html#id20", 0, None),
    ("stock_board_industry_cons_em", "行业板块成分(东财)", "板块数据,行业板块", "获取东方财富行业板块成分股", "/api/v1/ak/stock-board-industry-cons-em", "https://akshare.akfamily.xyz/data/stock/stock.html#id21", 0, None),
    ("stock_board_concept_name_em", "概念板块列表(东财)", "板块数据,概念板块", "获取东方财富概念板块名称列表", "/api/v1/ak/stock-board-concept-name-em", "https://akshare.akfamily.xyz/data/stock/stock.html#id22", 0, None),
    ("stock_board_concept_cons_em", "概念板块成分(东财)", "板块数据,概念板块", "获取东方财富概念板块成分股", "/api/v1/ak/stock-board-concept-cons-em", "https://akshare.akfamily.xyz/data/stock/stock.html#id23", 0, None),
    # ====== 资金流向 ======
    ("stock_individual_fund_flow", "个股资金流向", "资金流向,个股", "获取个股资金流向数据", "/api/v1/ak/stock-individual-fund-flow", "https://akshare.akfamily.xyz/data/stock/stock.html#id30", 0, None),
    ("stock_market_fund_flow", "大盘资金流向", "资金流向,大盘", "获取大盘资金流向数据", "/api/v1/ak/stock-market-fund-flow", "https://akshare.akfamily.xyz/data/stock/stock.html#id31", 0, None),
    ("stock_sector_fund_flow_rank", "板块资金流排名", "资金流向,板块", "获取板块资金流排名", "/api/v1/ak/stock-sector-fund-flow-rank", "https://akshare.akfamily.xyz/data/stock/stock.html#id32", 0, None),
    # ====== 龙虎榜 ======
    ("stock_lhb_detail_em", "龙虎榜详情(东财)", "龙虎榜,详情", "获取东方财富龙虎榜详情数据", "/api/v1/ak/stock-lhb-detail-em", "https://akshare.akfamily.xyz/data/stock/stock.html#id40", 0, None),
    ("stock_lhb_stock_statistic_em", "龙虎榜个股统计(东财)", "龙虎榜,统计", "获取龙虎榜个股上榜统计", "/api/v1/ak/stock-lhb-stock-statistic-em", "https://akshare.akfamily.xyz/data/stock/stock.html#id41", 0, None),
    # ====== 北向资金/港股通 ======
    ("stock_hsgt_north_net_flow_in_em", "北向资金净流入(东财)", "北向资金,净流入", "获取北向资金净流入数据", "/api/v1/ak/stock-hsgt-north-net-flow-in-em", "https://akshare.akfamily.xyz/data/stock/stock.html#id50", 0, None),
    ("stock_hsgt_north_acc_flow_in_em", "北向资金累计流入(东财)", "北向资金,累计", "获取北向资金累计流入数据", "/api/v1/ak/stock-hsgt-north-acc-flow-in-em", "https://akshare.akfamily.xyz/data/stock/stock.html#id51", 0, None),
    ("stock_hsgt_hold_stock_em", "北向持股明细(东财)", "北向资金,持股", "获取北向资金持股数据", "/api/v1/ak/stock-hsgt-hold-stock-em", "https://akshare.akfamily.xyz/data/stock/stock.html#id52", 0, None),
    # ====== 宏观经济 ======
    ("macro_china_cpi", "中国CPI", "宏观经济,价格指数", "获取中国居民消费价格指数(CPI)", "/api/v1/ak/macro-china-cpi", "https://akshare.akfamily.xyz/data/macro/macro.html#id1", 0, None),
    ("macro_china_ppi", "中国PPI", "宏观经济,价格指数", "获取中国工业品出厂价格指数(PPI)", "/api/v1/ak/macro-china-ppi", "https://akshare.akfamily.xyz/data/macro/macro.html#id2", 0, None),
    ("macro_china_gdp", "中国GDP", "宏观经济,国民经济", "获取中国国内生产总值数据", "/api/v1/ak/macro-china-gdp", "https://akshare.akfamily.xyz/data/macro/macro.html#id3", 0, None),
    ("macro_china_pmi", "中国PMI", "宏观经济,景气度", "获取中国采购经理指数(PMI)", "/api/v1/ak/macro-china-pmi", "https://akshare.akfamily.xyz/data/macro/macro.html#id4", 0, None),
    ("macro_china_money_supply", "货币供应量", "宏观经济,货币供应量", "获取中国货币供应量数据", "/api/v1/ak/macro-china-money-supply", "https://akshare.akfamily.xyz/data/macro/macro.html#id5", 0, None),
    # ====== 新闻/舆情 ======
    ("stock_news_em", "个股新闻(东财)", "新闻舆情,个股", "获取东方财富个股新闻数据", "/api/v1/ak/stock-news-em", "https://akshare.akfamily.xyz/data/stock/stock.html#id60", 0, None),
    ("news_cctv", "新闻联播文字稿", "新闻舆情,宏观", "获取新闻联播文字稿", "/api/v1/ak/news-cctv", "https://akshare.akfamily.xyz/data/others/others.html#id1", 0, None),
    # ====== 可转债 ======
    ("bond_cb_jsl", "可转债实时数据(集思录)", "可转债,实时数据", "获取集思录可转债实时数据", "/api/v1/ak/bond-cb-jsl", "https://akshare.akfamily.xyz/data/bond/bond.html#id1", 0, None),
    ("bond_cb_redeem_jsl", "可转债强赎(集思录)", "可转债,强赎", "获取集思录可转债强赎数据", "/api/v1/ak/bond-cb-redeem-jsl", "https://akshare.akfamily.xyz/data/bond/bond.html#id2", 0, None),
]


def seed_data_sources(db: Session) -> None:
    """将所有数据源信息写入数据库。

    按 (provider, api_name) 检查，已存在跳过。
    支持多 provider 的种子数据。
    """
    # Tushare 数据源
    for row in _TUSHARE_SEED_DATA:
        api_name = row[0]
        existing = db.query(DataSource).filter(
            DataSource.provider == "tushare",
            DataSource.api_name == api_name,
        ).first()
        if existing:
            continue

        ds = DataSource(
            provider="tushare",
            api_name=row[0],
            title=row[1],
            category=row[2],
            description=row[3],
            proxy_path=row[4],
            doc_url=row[5],
            has_local_table=row[6],
            local_table_name=row[7],
        )
        db.add(ds)

    # AKShare 数据源
    for row in _AKSHARE_SEED_DATA:
        api_name = row[0]
        existing = db.query(DataSource).filter(
            DataSource.provider == "akshare",
            DataSource.api_name == api_name,
        ).first()
        if existing:
            continue

        ds = DataSource(
            provider="akshare",
            api_name=row[0],
            title=row[1],
            category=row[2],
            description=row[3],
            proxy_path=row[4],
            doc_url=row[5],
            has_local_table=row[6],
            local_table_name=row[7],
        )
        db.add(ds)

    # 修正本地表标记（覆盖已有记录）
    for api_name, table_name in _LOCAL_TABLE_MAP.items():
        ds = db.query(DataSource).filter(
            DataSource.provider == "tushare",
            DataSource.api_name == api_name,
        ).first()
        if ds and (ds.has_local_table != 1 or ds.local_table_name != table_name):
            ds.has_local_table = 1
            ds.local_table_name = table_name

    # 给老数据补 provider 字段（兼容存量数据）
    legacy = db.query(DataSource).filter(DataSource.provider.is_(None)).all()
    for ds in legacy:
        ds.provider = "tushare"

    db.commit()


# 需要有本地表的接口映射
_LOCAL_TABLE_MAP = {
    "stock_basic": "stock_basic",
    "daily": "stock_daily",
    "weekly": "stock_weekly",
    "monthly": "stock_monthly",
    "daily_basic": "stock_daily_basic",
    "stk_limit": "stock_limit",
    "fina_indicator": "stock_fina_indicator",
    "top_list": "top_list",
    "top_inst": "top_inst",
    "ths_index": "ths_index",
    "ths_daily": "ths_daily",
    "ths_member": "ths_member",
    "moneyflow": "stock_moneyflow",
    "moneyflow_hsgt": "moneyflow_hsgt",
    "moneyflow_ind_ths": "sector_moneyflow_industry",
    "index_basic": "index_basic",
    "index_daily": "index_daily",
    # 新增分析表
    "limit_list_d": "limit_list_d",
    "limit_step": "limit_step",
    "limit_list_ths": "limit_list_ths",
    "dc_concept": "dc_concept",
    "dc_concept_cons": "dc_concept_cons",
    "ths_hot": "ths_hot",
    "dc_hot": "dc_hot",
    "hk_hold": "hk_hold",
    "stk_holdernumber": "stk_holdernumber",
    "stk_holdertrade": "stk_holdertrade",
    "cyq_perf": "cyq_perf",
    "margin_detail": "margin_detail",
    "broker_recommend": "broker_recommend",
    "report_rc": "report_rc",
    "index_weight": "index_weight",
    "index_dailybasic": "index_dailybasic",
    "sw_daily": "sw_daily",
    "cn_cpi": "cn_cpi",
    "cn_pmi": "cn_pmi",
    "shibor_lpr": "shibor_lpr",
    "sf_month": "sf_month",
    "etf_basic": "etf_basic",
    "etf_share_size": "etf_share_size",
    "cb_basic": "cb_basic",
    "cb_daily": "cb_daily_local",
}
