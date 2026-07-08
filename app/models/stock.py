from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.db.base import Base


class StockBasic(Base):
    """股票基础信息"""

    __tablename__ = "stock_basic"

    ts_code = Column(String(20), primary_key=True, comment="Tushare 代码，如 000001.SZ")
    symbol = Column(String(20), nullable=True, comment="股票代码")
    name = Column(String(100), nullable=True, comment="股票名称")
    area = Column(String(50), nullable=True, comment="地域")
    industry = Column(String(50), nullable=True, comment="所属行业")
    fullname = Column(String(200), nullable=True, comment="股票全称")
    enname = Column(String(200), nullable=True, comment="英文全称")
    cnspell = Column(String(50), nullable=True, comment="拼音缩写")
    market = Column(String(20), nullable=True, comment="市场类型")
    exchange = Column(String(20), nullable=True, comment="交易所代码")
    curr_type = Column(String(10), nullable=True, comment="交易货币")
    list_status = Column(String(1), nullable=True, comment="上市状态")
    list_date = Column(Date, nullable=True, comment="上市日期")
    delist_date = Column(Date, nullable=True, comment="退市日期")
    is_hs = Column(String(1), nullable=True, comment="是否沪深港通标的")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class StockDaily(Base):
    """股票日线行情"""

    __tablename__ = "stock_daily"

    ts_code = Column(String(20), primary_key=True, comment="Tushare 代码")
    trade_date = Column(Date, primary_key=True, comment="交易日")

    open = Column(Numeric(12, 4), nullable=True, comment="开盘价")
    high = Column(Numeric(12, 4), nullable=True, comment="最高价")
    low = Column(Numeric(12, 4), nullable=True, comment="最低价")
    close = Column(Numeric(12, 4), nullable=True, comment="收盘价")
    pre_close = Column(Numeric(12, 4), nullable=True, comment="昨收价")
    change = Column(Numeric(12, 4), nullable=True, comment="涨跌额")
    pct_chg = Column(Numeric(20, 4), nullable=True, comment="涨跌幅")
    vol = Column(Numeric(20, 4), nullable=True, comment="成交量（手）")
    amount = Column(Numeric(20, 4), nullable=True, comment="成交额（千元）")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uix_stock_daily"),
    )


class StockWeekly(Base):
    """股票周线行情"""

    __tablename__ = "stock_weekly"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True, comment="当周最后一个交易日")

    open = Column(Numeric(12, 4), nullable=True)
    high = Column(Numeric(12, 4), nullable=True)
    low = Column(Numeric(12, 4), nullable=True)
    close = Column(Numeric(12, 4), nullable=True)
    pre_close = Column(Numeric(12, 4), nullable=True)
    change = Column(Numeric(12, 4), nullable=True)
    pct_chg = Column(Numeric(20, 4), nullable=True)
    vol = Column(Numeric(20, 4), nullable=True)
    amount = Column(Numeric(20, 4), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uix_stock_weekly"),
    )


class StockMonthly(Base):
    """股票月线行情"""

    __tablename__ = "stock_monthly"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True, comment="当月最后一个交易日")

    open = Column(Numeric(12, 4), nullable=True)
    high = Column(Numeric(12, 4), nullable=True)
    low = Column(Numeric(12, 4), nullable=True)
    close = Column(Numeric(12, 4), nullable=True)
    pre_close = Column(Numeric(12, 4), nullable=True)
    change = Column(Numeric(12, 4), nullable=True)
    pct_chg = Column(Numeric(20, 4), nullable=True)
    vol = Column(Numeric(20, 4), nullable=True)
    amount = Column(Numeric(20, 4), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uix_stock_monthly"),
    )


class StockYearly(Base):
    """股票年线行情"""

    __tablename__ = "stock_yearly"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True, comment="当年最后一个交易日")

    open = Column(Numeric(12, 4), nullable=True)
    high = Column(Numeric(12, 4), nullable=True)
    low = Column(Numeric(12, 4), nullable=True)
    close = Column(Numeric(12, 4), nullable=True)
    pre_close = Column(Numeric(12, 4), nullable=True)
    change = Column(Numeric(12, 4), nullable=True)
    pct_chg = Column(Numeric(20, 4), nullable=True)
    vol = Column(Numeric(20, 4), nullable=True)
    amount = Column(Numeric(20, 4), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uix_stock_yearly"),
    )


class StockDailyBasic(Base):
    """股票每日指标/因子（daily_basic）"""

    __tablename__ = "stock_daily_basic"

    ts_code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True)

    close = Column(Numeric(12, 4), nullable=True, comment="当日收盘价")
    turnover_rate = Column(Numeric(20, 4), nullable=True, comment="换手率")
    turnover_rate_f = Column(Numeric(20, 4), nullable=True, comment="换手率（自由流通股）")
    volume_ratio = Column(Numeric(20, 4), nullable=True, comment="量比")
    pe = Column(Numeric(20, 4), nullable=True, comment="市盈率")
    pe_ttm = Column(Numeric(20, 4), nullable=True, comment="市盈率 TTM")
    pb = Column(Numeric(20, 4), nullable=True, comment="市净率")
    ps = Column(Numeric(20, 4), nullable=True, comment="市销率")
    ps_ttm = Column(Numeric(20, 4), nullable=True, comment="市销率 TTM")
    dv_ratio = Column(Numeric(20, 4), nullable=True, comment="股息率")
    dv_ttm = Column(Numeric(20, 4), nullable=True, comment="股息率 TTM")
    total_share = Column(Numeric(20, 4), nullable=True, comment="总股本（万股）")
    float_share = Column(Numeric(20, 4), nullable=True, comment="流通股本（万股）")
    free_share = Column(Numeric(20, 4), nullable=True, comment="自由流通股本（万股）")
    total_mv = Column(Numeric(20, 4), nullable=True, comment="总市值（万元）")
    circ_mv = Column(Numeric(20, 4), nullable=True, comment="流通市值（万元）")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uix_stock_daily_basic"),
    )


class StockFinaIndicator(Base):
    """股票财务指标（季度）"""

    __tablename__ = "stock_fina_indicator"

    ts_code = Column(String(20), primary_key=True)
    ann_date = Column(Date, nullable=True, comment="公告日期")
    end_date = Column(Date, primary_key=True, comment="报告期")

    eps = Column(Numeric(20, 4), nullable=True, comment="基本每股收益")
    dt_eps = Column(Numeric(20, 4), nullable=True, comment="稀释每股收益")
    total_revenue_ps = Column(Numeric(20, 4), nullable=True, comment="营业总收入每股")
    revenue_ps = Column(Numeric(20, 4), nullable=True, comment="营业收入每股")
    capital_rese_ps = Column(Numeric(20, 4), nullable=True, comment="资本公积每股")
    surplus_rese_ps = Column(Numeric(20, 4), nullable=True, comment="盈余公积每股")
    undist_profit_ps = Column(Numeric(20, 4), nullable=True, comment="未分配利润每股")
    extra_item = Column(Numeric(20, 4), nullable=True, comment="非经常性损益")
    profit_dedt = Column(Numeric(20, 4), nullable=True, comment="扣除非经常性损益后净利润")
    gross_margin = Column(Numeric(20, 4), nullable=True, comment="毛利")
    current_ratio = Column(Numeric(20, 4), nullable=True, comment="流动比率")
    quick_ratio = Column(Numeric(20, 4), nullable=True, comment="速动比率")
    cash_ratio = Column(Numeric(20, 4), nullable=True, comment="保守速动比率")
    invturn_days = Column(Numeric(20, 4), nullable=True, comment="存货周转天数")
    arturn_days = Column(Numeric(20, 4), nullable=True, comment="应收账款周转天数")
    inv_turn = Column(Numeric(20, 4), nullable=True, comment="存货周转率")
    ar_turn = Column(Numeric(20, 4), nullable=True, comment="应收账款周转率")
    ca_turn = Column(Numeric(20, 4), nullable=True, comment="流动资产周转率")
    fa_turn = Column(Numeric(20, 4), nullable=True, comment="固定资产周转率")
    assets_turn = Column(Numeric(20, 4), nullable=True, comment="总资产周转率")
    op_income = Column(Numeric(20, 4), nullable=True, comment="经营活动净收益")
    valuechange_income = Column(Numeric(20, 4), nullable=True, comment="价值变动净收益")
    interst_income = Column(Numeric(20, 4), nullable=True, comment="利息费用")
    daa = Column(Numeric(20, 4), nullable=True, comment="折旧与摊销")
    ebit = Column(Numeric(20, 4), nullable=True, comment="息税前利润")
    ebitda = Column(Numeric(20, 4), nullable=True, comment="息税折旧摊销前利润")
    fcff = Column(Numeric(20, 4), nullable=True, comment="企业自由现金流量")
    fcfe = Column(Numeric(20, 4), nullable=True, comment="股权自由现金流量")
    current_exint = Column(Numeric(20, 4), nullable=True, comment="无息流动负债")
    noncurrent_exint = Column(Numeric(20, 4), nullable=True, comment="无息非流动负债")
    interestdebt = Column(Numeric(20, 4), nullable=True, comment="带息债务")
    netdebt = Column(Numeric(20, 4), nullable=True, comment="净债务")
    tangible_asset = Column(Numeric(20, 4), nullable=True, comment="有形资产")
    working_capital = Column(Numeric(20, 4), nullable=True, comment="营运资金")
    networking_capital = Column(Numeric(20, 4), nullable=True, comment="营运流动资本")
    invest_capital = Column(Numeric(20, 4), nullable=True, comment="全部投入资本")
    retained_earnings = Column(Numeric(20, 4), nullable=True, comment="留存收益")
    diluted2_eps = Column(Numeric(20, 4), nullable=True, comment="期末摊薄每股收益")
    bps = Column(Numeric(20, 4), nullable=True, comment="每股净资产")
    ocfps = Column(Numeric(20, 4), nullable=True, comment="每股经营活动产生的现金流量净额")
    retainedps = Column(Numeric(20, 4), nullable=True, comment="每股留存收益")
    cfps = Column(Numeric(20, 4), nullable=True, comment="每股现金流量净额")
    ebit_ps = Column(Numeric(20, 4), nullable=True, comment="每股息税前利润")
    fcfps = Column(Numeric(20, 4), nullable=True, comment="每股企业自由现金流量")
    netprofit_margin = Column(Numeric(20, 4), nullable=True, comment="销售净利率")
    grossprofit_margin = Column(Numeric(20, 4), nullable=True, comment="销售毛利率")
    cogs_of_sales = Column(Numeric(20, 4), nullable=True, comment="销售成本率")
    expense_of_sales = Column(Numeric(20, 4), nullable=True, comment="销售期间费用率")
    profit_to_gr = Column(Numeric(20, 4), nullable=True, comment="净利润/营业总收入")
    saleexp_to_gr = Column(Numeric(20, 4), nullable=True, comment="销售费用/营业总收入")
    adminexp_of_gr = Column(Numeric(20, 4), nullable=True, comment="管理费用/营业总收入")
    finaexp_of_gr = Column(Numeric(20, 4), nullable=True, comment="财务费用/营业总收入")
    impai_ttm = Column(Numeric(20, 4), nullable=True, comment="资产减值损失/营业总收入")
    gc_of_gr = Column(Numeric(20, 4), nullable=True, comment="营业总成本/营业总收入")
    op_of_gr = Column(Numeric(20, 4), nullable=True, comment="营业利润/营业总收入")
    ebit_of_gr = Column(Numeric(20, 4), nullable=True, comment="息税前利润/营业总收入")
    roe = Column(Numeric(20, 4), nullable=True, comment="净资产收益率")
    roe_waa = Column(Numeric(20, 4), nullable=True, comment="加权平均净资产收益率")
    roe_dt = Column(Numeric(20, 4), nullable=True, comment="净资产收益率（扣除非经常损益）")
    roa = Column(Numeric(20, 4), nullable=True, comment="总资产报酬率")
    npta = Column(Numeric(20, 4), nullable=True, comment="总资产净利润")
    roic = Column(Numeric(20, 4), nullable=True, comment="投入资本回报率")
    roe_yearly = Column(Numeric(20, 4), nullable=True, comment="年化净资产收益率")
    roa2_yearly = Column(Numeric(20, 4), nullable=True, comment="年化总资产报酬率")
    roe_avg = Column(Numeric(20, 4), nullable=True, comment="平均净资产收益率(增发条件)")
    opincome_of_ebt = Column(Numeric(20, 4), nullable=True, comment="经营活动净收益/利润总额")
    investincome_of_ebt = Column(Numeric(20, 4), nullable=True, comment="价值变动净收益/利润总额")
    non_op_income = Column(Numeric(20, 4), nullable=True, comment="营业外收支净额/利润总额")
    tax_to_ebt = Column(Numeric(20, 4), nullable=True, comment="所得税/利润总额")
    deductedprofit_of_sales = Column(Numeric(20, 4), nullable=True, comment="扣除非经常损益后的净利润/营业收入")
    grossprofit_to_asset = Column(Numeric(20, 4), nullable=True, comment="总资产毛利润率")
    grossprofit_to_equity = Column(Numeric(20, 4), nullable=True, comment="净资产毛利润率")
    bpm = Column(Numeric(20, 4), nullable=True, comment="营业利润率")
    netprofit_to_asset = Column(Numeric(20, 4), nullable=True, comment="总资产净利率")
    ocf_to_asset = Column(Numeric(20, 4), nullable=True, comment="总资产现金回收率")
    ocf_to_sales = Column(Numeric(20, 4), nullable=True, comment="销售现金比率")
    assets_to_eqt = Column(Numeric(20, 4), nullable=True, comment="权益乘数")
    dp_assets_to_eqt = Column(Numeric(20, 4), nullable=True, comment="权益乘数（杜邦分析）")
    ca_to_assets = Column(Numeric(20, 4), nullable=True, comment="流动资产/总资产")
    nca_to_assets = Column(Numeric(20, 4), nullable=True, comment="非流动资产/总资产")
    tbassets_to_totalassets = Column(Numeric(20, 4), nullable=True, comment="有形资产/总资产")
    int_to_talcap = Column(Numeric(20, 4), nullable=True, comment="带息债务/全部投入资本")
    eqt_to_talcapital = Column(Numeric(20, 4), nullable=True, comment="归属于母公司的股东权益/全部投入资本")
    currentdebt_to_debt = Column(Numeric(20, 4), nullable=True, comment="流动负债/负债合计")
    longdeb_to_debt = Column(Numeric(20, 4), nullable=True, comment="非流动负债/负债合计")
    ocf_to_shortdebt = Column(Numeric(20, 4), nullable=True, comment="经营活动产生的现金流量净额/流动负债")
    debt_to_eqt = Column(Numeric(20, 4), nullable=True, comment="产权比率")
    eqt_to_debt = Column(Numeric(20, 4), nullable=True, comment="归属于母公司的股东权益/负债合计")
    eqt_to_interestdebt = Column(Numeric(20, 4), nullable=True, comment="归属于母公司的股东权益/带息债务")
    tangibleasset_to_debt = Column(Numeric(20, 4), nullable=True, comment="有形资产/负债合计")
    tangasset_to_intdebt = Column(Numeric(20, 4), nullable=True, comment="有形资产/带息债务")
    tangibleasset_to_netdebt = Column(Numeric(20, 4), nullable=True, comment="有形资产/净债务")
    ocf_to_debt = Column(Numeric(20, 4), nullable=True, comment="经营活动产生的现金流量净额/负债合计")
    ocf_to_interestdebt = Column(Numeric(20, 4), nullable=True, comment="经营活动产生的现金流量净额/带息债务")
    ocf_to_netdebt = Column(Numeric(20, 4), nullable=True, comment="经营活动产生的现金流量净额/净债务")
    ebit_to_interest = Column(Numeric(20, 4), nullable=True, comment="已获利息倍数")
    longdebt_to_workingcapital = Column(Numeric(20, 4), nullable=True, comment="长期债务与营运资金比率")
    ebitda_to_debt = Column(Numeric(20, 4), nullable=True, comment="息税折旧摊销前利润/负债合计")
    fix_assets_ratio = Column(Numeric(20, 4), nullable=True, comment="固定资产占比")
    basic_eps_yoy = Column(Numeric(20, 4), nullable=True, comment="基本每股收益同比增长率")
    dt_eps_yoy = Column(Numeric(20, 4), nullable=True, comment="稀释每股收益同比增长率")
    cfps_yoy = Column(Numeric(20, 4), nullable=True, comment="每股现金流量净额同比增长率")
    op_yoy = Column(Numeric(20, 4), nullable=True, comment="营业利润同比增长率")
    ebt_yoy = Column(Numeric(20, 4), nullable=True, comment="利润总额同比增长率")
    netprofit_yoy = Column(Numeric(20, 4), nullable=True, comment="净利润同比增长率")
    dt_netprofit_yoy = Column(Numeric(20, 4), nullable=True, comment="稀释每股收益同比增长率")
    roe_yoy = Column(Numeric(20, 4), nullable=True, comment="净资产收益率(摊薄)同比增长率")
    bps_yoy = Column(Numeric(20, 4), nullable=True, comment="每股净资产相对年初增长率")
    assets_yoy = Column(Numeric(20, 4), nullable=True, comment="资产总计相对年初增长率")
    eqt_yoy = Column(Numeric(20, 4), nullable=True, comment="归属母公司的股东权益相对年初增长率")
    tr_yoy = Column(Numeric(20, 4), nullable=True, comment="营业总收入同比增长率")
    or_yoy = Column(Numeric(20, 4), nullable=True, comment="营业收入同比增长率")
    q_sales_yoy = Column(Numeric(20, 4), nullable=True, comment="销售收入同比增长率")
    q_sales_qoq = Column(Numeric(20, 4), nullable=True, comment="销售收入环比增长率")
    q_op_yoy = Column(Numeric(20, 4), nullable=True, comment="营业利润同比增长率")
    q_op_qoq = Column(Numeric(20, 4), nullable=True, comment="营业利润环比增长率")
    equity_yoy = Column(Numeric(20, 4), nullable=True, comment="净资产同比增长率")
    rd_exp = Column(Numeric(20, 4), nullable=True, comment="研发费用")

    update_flag = Column(String(1), nullable=True, comment="更新标识")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("ts_code", "end_date", name="uix_stock_fina_indicator"),
    )


class SectorMoneyflowIndustry(Base):
    """同花顺行业板块资金流"""

    __tablename__ = "sector_moneyflow_industry"

    ts_code = Column(String(20), primary_key=True, comment="板块代码，如 881145.TI")
    trade_date = Column(Date, primary_key=True, comment="交易日期")

    industry = Column(String(50), nullable=True, comment="行业名称")
    lead_stock = Column(String(50), nullable=True, comment="龙头股")
    close = Column(Numeric(20, 4), nullable=True, comment="板块指数收盘价")
    pct_change = Column(Numeric(20, 4), nullable=True, comment="板块涨跌幅%")
    company_num = Column(Integer, nullable=True, comment="成分股数量")
    pct_change_stock = Column(Numeric(20, 4), nullable=True, comment="领涨股涨跌幅%")
    close_price = Column(Numeric(20, 4), nullable=True, comment="领涨股收盘价")
    net_buy_amount = Column(Numeric(20, 4), nullable=True, comment="净流入-买入金额（亿元）")
    net_sell_amount = Column(Numeric(20, 4), nullable=True, comment="净流入-卖出金额（亿元）")
    net_amount = Column(Numeric(20, 4), nullable=True, comment="净流入金额（亿元）")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uix_sector_moneyflow_industry"),
    )


class SectorMoneyflowConcept(Base):
    """同花顺概念板块资金流"""

    __tablename__ = "sector_moneyflow_concept"

    ts_code = Column(String(20), primary_key=True, comment="板块代码，如 885860.TI")
    trade_date = Column(Date, primary_key=True, comment="交易日期")

    name = Column(String(50), nullable=True, comment="概念名称")
    lead_stock = Column(String(50), nullable=True, comment="龙头股")
    close_price = Column(Numeric(20, 4), nullable=True, comment="领涨股收盘价")
    pct_change = Column(Numeric(20, 4), nullable=True, comment="板块涨跌幅%")
    industry_index = Column(Numeric(20, 4), nullable=True, comment="行业指数")
    company_num = Column(Integer, nullable=True, comment="成分股数量")
    pct_change_stock = Column(Numeric(20, 4), nullable=True, comment="领涨股涨跌幅%")
    net_buy_amount = Column(Numeric(20, 4), nullable=True, comment="净流入-买入金额（亿元）")
    net_sell_amount = Column(Numeric(20, 4), nullable=True, comment="净流入-卖出金额（亿元）")
    net_amount = Column(Numeric(20, 4), nullable=True, comment="净流入金额（亿元）")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uix_sector_moneyflow_concept"),
    )


# 兼容旧导入名称
StockKline = StockDaily
