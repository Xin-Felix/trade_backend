"""Tushare 代理接口统一入口。

所有接口直接透传 Tushare Pro API 数据，不经过本地数据库。
每个接口一个文件，方便维护和查找。
挂载在 /api/v1/ts 前缀下。
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import require_feature

# 一、股票基础/行情
from .stock_basic import router as stock_basic_router
from .trade_cal import router as trade_cal_router
from .daily import router as daily_router
from .pro_bar import router as pro_bar_router
from .weekly import router as weekly_router
from .monthly import router as monthly_router
from .adj_factor import router as adj_factor_router
from .suspend_d import router as suspend_d_router
from .daily_basic import router as daily_basic_router
from .stk_limit import router as stk_limit_router
from .namechange import router as namechange_router
from .stk_premarket import router as stk_premarket_router
from .stk_weekly_monthly import router as stk_weekly_monthly_router
from .stk_week_month_adj import router as stk_week_month_adj_router
from .stk_mins import router as stk_mins_router
from .rt_min import router as rt_min_router
from .rt_k import router as rt_k_router
from .rt_min_daily import router as rt_min_daily_router
from .bak_daily import router as bak_daily_router
from .bak_basic import router as bak_basic_router
from .bse_mapping import router as bse_mapping_router
from .st import router as st_router
from .ggt_daily import router as ggt_daily_router
from .hsgt_top10 import router as hsgt_top10_router
from .ggt_top10 import router as ggt_top10_router

# 二、财务数据
from .fina_indicator import router as fina_indicator_router
from .income import router as income_router
from .balancesheet import router as balancesheet_router
from .cashflow import router as cashflow_router
from .forecast import router as forecast_router
from .express import router as express_router
from .dividend import router as dividend_router
from .fina_mainbz import router as fina_mainbz_router
from .fina_audit import router as fina_audit_router
from .disclosure_date import router as disclosure_date_router

# 三、参考数据
from .top10_holders import router as top10_holders_router
from .top10_floatholders import router as top10_floatholders_router
from .stk_holdernumber import router as stk_holdernumber_router
from .stk_holdertrade import router as stk_holdertrade_router
from .pledge_stat import router as pledge_stat_router
from .pledge_detail import router as pledge_detail_router
from .repurchase import router as repurchase_router
from .share_float import router as share_float_router
from .block_trade import router as block_trade_router
from .new_share import router as new_share_router
from .stock_company import router as stock_company_router
from .stk_managers import router as stk_managers_router
from .stk_rewards import router as stk_rewards_router
from .stock_hsgt import router as stock_hsgt_router
from .stock_st import router as stock_st_router
from .stk_account import router as stk_account_router
from .stk_account_old import router as stk_account_old_router
from .stk_high_shock import router as stk_high_shock_router
from .stk_ah_comparison import router as stk_ah_comparison_router

# 四、打板/题材/龙虎榜
from .top_list import router as top_list_router
from .top_inst import router as top_inst_router
from .limit_list_d import router as limit_list_d_router
from .limit_step import router as limit_step_router
from .limit_cpt_list import router as limit_cpt_list_router
from .limit_list_ths import router as limit_list_ths_router
from .kpl_list import router as kpl_list_router
from .kpl_concept_cons import router as kpl_concept_cons_router
from .ths_index import router as ths_index_router
from .ths_daily import router as ths_daily_router
from .ths_member import router as ths_member_router
from .ths_hot import router as ths_hot_router
from .dc_index import router as dc_index_router
from .dc_member import router as dc_member_router
from .dc_daily import router as dc_daily_router
from .dc_hot import router as dc_hot_router
from .dc_concept import router as dc_concept_router
from .dc_concept_cons import router as dc_concept_cons_router
from .tdx_index import router as tdx_index_router
from .tdx_member import router as tdx_member_router
from .tdx_daily import router as tdx_daily_router
from .hm_list import router as hm_list_router
from .hm_detail import router as hm_detail_router
from .stk_auction import router as stk_auction_router
from .stk_auction_o import router as stk_auction_o_router
from .stk_auction_c import router as stk_auction_c_router
from .broker_recommend import router as broker_recommend_router

# 五、资金流向
from .moneyflow import router as moneyflow_router
from .moneyflow_hsgt import router as moneyflow_hsgt_router
from .moneyflow_cnt_ths import router as moneyflow_cnt_ths_router
from .moneyflow_ind_ths import router as moneyflow_ind_ths_router
from .moneyflow_ind_dc import router as moneyflow_ind_dc_router
from .moneyflow_mkt_dc import router as moneyflow_mkt_dc_router
from .moneyflow_ths import router as moneyflow_ths_router
from .moneyflow_dc import router as moneyflow_dc_router

# 六、两融
from .margin import router as margin_router
from .margin_detail import router as margin_detail_router
from .margin_secs import router as margin_secs_router
from .slb_len import router as slb_len_router
from .slb_sec import router as slb_sec_router
from .slb_sec_detail import router as slb_sec_detail_router
from .slb_len_mm import router as slb_len_mm_router

# 七、特色数据
from .cyq_perf import router as cyq_perf_router
from .cyq_chips import router as cyq_chips_router
from .stk_factor import router as stk_factor_router
from .stk_factor_pro import router as stk_factor_pro_router
from .stk_nineturn import router as stk_nineturn_router
from .hk_hold import router as hk_hold_router
from .stk_surv import router as stk_surv_router
from .report_rc import router as report_rc_router
from .stk_alert import router as stk_alert_router
from .stk_shock import router as stk_shock_router
from .ccass_hold import router as ccass_hold_router
from .ccass_hold_detail import router as ccass_hold_detail_router

# 八、ETF/基金
from .fund_basic import router as fund_basic_router
from .fund_daily import router as fund_daily_router
from .fund_nav import router as fund_nav_router
from .fund_share import router as fund_share_router
from .fund_portfolio import router as fund_portfolio_router
from .fund_div import router as fund_div_router
from .fund_manager import router as fund_manager_router
from .fund_adj import router as fund_adj_router
from .fund_company import router as fund_company_router
from .fund_factor_pro import router as fund_factor_pro_router
from .mkt_idx_bmk import router as mkt_idx_bmk_router
from .etf_basic import router as etf_basic_router
from .etf_index import router as etf_index_router
from .etf_share_size import router as etf_share_size_router
from .etf_sh_cons import router as etf_sh_cons_router
from .etf_sz_cons import router as etf_sz_cons_router
from .etf_mins import router as etf_mins_router
from .rt_etf_k import router as rt_etf_k_router
from .rt_etf_min import router as rt_etf_min_router
from .rt_etf_min_daily import router as rt_etf_min_daily_router
from .rt_etf_sz_iopv import router as rt_etf_sz_iopv_router
from .idx_anns import router as idx_anns_router

# 九、指数
from .index_basic import router as index_basic_router
from .index_daily import router as index_daily_router
from .index_weekly import router as index_weekly_router
from .index_monthly import router as index_monthly_router
from .index_weight import router as index_weight_router
from .index_dailybasic import router as index_dailybasic_router
from .index_classify import router as index_classify_router
from .index_member_all import router as index_member_all_router
from .index_global import router as index_global_router
from .sw_daily import router as sw_daily_router
from .sw_mins import router as sw_mins_router
from .rt_sw_k import router as rt_sw_k_router
from .rt_idx_k import router as rt_idx_k_router
from .rt_idx_min import router as rt_idx_min_router
from .idx_mins import router as idx_mins_router
from .idx_factor_pro import router as idx_factor_pro_router
from .ci_daily import router as ci_daily_router
from .ci_index_member import router as ci_index_member_router
from .daily_info import router as daily_info_router
from .sz_daily_info import router as sz_daily_info_router

# 十、宏观/新闻/语料
from .news import router as news_router
from .major_news import router as major_news_router
from .cctv_news import router as cctv_news_router
from .shibor import router as shibor_router
from .shibor_quote import router as shibor_quote_router
from .shibor_lpr import router as shibor_lpr_router
from .libor import router as libor_router
from .hibor import router as hibor_router
from .gz_index import router as gz_index_router
from .wz_index import router as wz_index_router
from .cn_cpi import router as cn_cpi_router
from .cn_ppi import router as cn_ppi_router
from .cn_gdp import router as cn_gdp_router
from .cn_m import router as cn_m_router
from .cn_pmi import router as cn_pmi_router
from .cn_schedule import router as cn_schedule_router
from .sf_month import router as sf_month_router
from .eco_cal import router as eco_cal_router
from .research_report import router as research_report_router
from .anns_d import router as anns_d_router
from .irm_qa_sh import router as irm_qa_sh_router
from .irm_qa_sz import router as irm_qa_sz_router
from .npr import router as npr_router
from .monetary_policy import router as monetary_policy_router
from .us_tycr import router as us_tycr_router
from .us_trltr import router as us_trltr_router
from .us_trycr import router as us_trycr_router
from .us_tbr import router as us_tbr_router
from .us_tltr import router as us_tltr_router

# 十一、债券/可转债
from .cb_basic import router as cb_basic_router
from .cb_issue import router as cb_issue_router
from .cb_daily import router as cb_daily_router
from .cb_factor_pro import router as cb_factor_pro_router
from .cb_rating import router as cb_rating_router
from .cb_call import router as cb_call_router
from .cb_share import router as cb_share_router
from .cb_price_chg import router as cb_price_chg_router
from .cb_rate import router as cb_rate_router
from .top10_cb_holders import router as top10_cb_holders_router
from .yc_cb import router as yc_cb_router
from .repo_daily import router as repo_daily_router
from .bond_blk import router as bond_blk_router
from .bond_blk_detail import router as bond_blk_detail_router
from .bc_otcqt import router as bc_otcqt_router
from .bc_bestotcqt import router as bc_bestotcqt_router

# 十二、外汇
from .fx_obasic import router as fx_obasic_router
from .fx_daily import router as fx_daily_router

# 十三、期权
from .opt_basic import router as opt_basic_router
from .opt_daily import router as opt_daily_router
from .opt_mins import router as opt_mins_router

# 十四、期货
from .fut_basic import router as fut_basic_router
from .fut_daily import router as fut_daily_router
from .fut_holding import router as fut_holding_router
from .fut_wsr import router as fut_wsr_router
from .fut_settle import router as fut_settle_router
from .fut_weekly_detail import router as fut_weekly_detail_router
from .fut_weekly_monthly import router as fut_weekly_monthly_router
from .fut_mapping import router as fut_mapping_router
from .fut_trade_cal import router as fut_trade_cal_router
from .fut_index_daily import router as fut_index_daily_router
from .ft_mins import router as ft_mins_router
from .ft_limit import router as ft_limit_router
from .rt_fut_min import router as rt_fut_min_router

# 十五、港股
from .hk_basic import router as hk_basic_router
from .hk_tradecal import router as hk_tradecal_router
from .hk_daily import router as hk_daily_router
from .hk_daily_adj import router as hk_daily_adj_router
from .hk_adjfactor import router as hk_adjfactor_router
from .hk_mins import router as hk_mins_router
from .hk_fina_indicator import router as hk_fina_indicator_router
from .hk_income import router as hk_income_router
from .hk_balancesheet import router as hk_balancesheet_router
from .hk_cashflow import router as hk_cashflow_router
from .rt_hk_k import router as rt_hk_k_router

# 十六、美股
from .us_basic import router as us_basic_router
from .us_tradecal import router as us_tradecal_router
from .us_daily import router as us_daily_router
from .us_daily_adj import router as us_daily_adj_router
from .us_adjfactor import router as us_adjfactor_router
from .us_fina_indicator import router as us_fina_indicator_router
from .us_income import router as us_income_router
from .us_balancesheet import router as us_balancesheet_router
from .us_cashflow import router as us_cashflow_router

# 十七、现货
from .sge_basic import router as sge_basic_router
from .sge_daily import router as sge_daily_router

# 十八、自选组合
from .p_save import router as p_save_router
from .p_list import router as p_list_router
from .p_delete import router as p_delete_router
from .p_get import router as p_get_router

# 汇总路由
router = APIRouter(dependencies=[Depends(require_feature("tushare_proxy", consume=True))])

# 一、股票基础/行情
router.include_router(stock_basic_router)
router.include_router(trade_cal_router)
router.include_router(daily_router)
router.include_router(pro_bar_router)
router.include_router(weekly_router)
router.include_router(monthly_router)
router.include_router(adj_factor_router)
router.include_router(suspend_d_router)
router.include_router(daily_basic_router)
router.include_router(stk_limit_router)
router.include_router(namechange_router)
router.include_router(stk_premarket_router)
router.include_router(stk_weekly_monthly_router)
router.include_router(stk_week_month_adj_router)
router.include_router(stk_mins_router)
router.include_router(rt_min_router)
router.include_router(rt_k_router)
router.include_router(rt_min_daily_router)
router.include_router(bak_daily_router)
router.include_router(bak_basic_router)
router.include_router(bse_mapping_router)
router.include_router(st_router)
router.include_router(ggt_daily_router)
router.include_router(hsgt_top10_router)
router.include_router(ggt_top10_router)
# 二、财务数据
router.include_router(fina_indicator_router)
router.include_router(income_router)
router.include_router(balancesheet_router)
router.include_router(cashflow_router)
router.include_router(forecast_router)
router.include_router(express_router)
router.include_router(dividend_router)
router.include_router(fina_mainbz_router)
router.include_router(fina_audit_router)
router.include_router(disclosure_date_router)
# 三、参考数据
router.include_router(top10_holders_router)
router.include_router(top10_floatholders_router)
router.include_router(stk_holdernumber_router)
router.include_router(stk_holdertrade_router)
router.include_router(pledge_stat_router)
router.include_router(pledge_detail_router)
router.include_router(repurchase_router)
router.include_router(share_float_router)
router.include_router(block_trade_router)
router.include_router(new_share_router)
router.include_router(stock_company_router)
router.include_router(stk_managers_router)
router.include_router(stk_rewards_router)
router.include_router(stock_hsgt_router)
router.include_router(stock_st_router)
router.include_router(stk_account_router)
router.include_router(stk_account_old_router)
router.include_router(stk_high_shock_router)
router.include_router(stk_ah_comparison_router)
# 四、打板/题材/龙虎榜
router.include_router(top_list_router)
router.include_router(top_inst_router)
router.include_router(limit_list_d_router)
router.include_router(limit_step_router)
router.include_router(limit_cpt_list_router)
router.include_router(limit_list_ths_router)
router.include_router(kpl_list_router)
router.include_router(kpl_concept_cons_router)
router.include_router(ths_index_router)
router.include_router(ths_daily_router)
router.include_router(ths_member_router)
router.include_router(ths_hot_router)
router.include_router(dc_index_router)
router.include_router(dc_member_router)
router.include_router(dc_daily_router)
router.include_router(dc_hot_router)
router.include_router(dc_concept_router)
router.include_router(dc_concept_cons_router)
router.include_router(tdx_index_router)
router.include_router(tdx_member_router)
router.include_router(tdx_daily_router)
router.include_router(hm_list_router)
router.include_router(hm_detail_router)
router.include_router(stk_auction_router)
router.include_router(stk_auction_o_router)
router.include_router(stk_auction_c_router)
router.include_router(broker_recommend_router)
# 五、资金流向
router.include_router(moneyflow_router)
router.include_router(moneyflow_hsgt_router)
router.include_router(moneyflow_cnt_ths_router)
router.include_router(moneyflow_ind_ths_router)
router.include_router(moneyflow_ind_dc_router)
router.include_router(moneyflow_mkt_dc_router)
router.include_router(moneyflow_ths_router)
router.include_router(moneyflow_dc_router)
# 六、两融
router.include_router(margin_router)
router.include_router(margin_detail_router)
router.include_router(margin_secs_router)
router.include_router(slb_len_router)
router.include_router(slb_sec_router)
router.include_router(slb_sec_detail_router)
router.include_router(slb_len_mm_router)
# 七、特色数据
router.include_router(cyq_perf_router)
router.include_router(cyq_chips_router)
router.include_router(stk_factor_router)
router.include_router(stk_factor_pro_router)
router.include_router(stk_nineturn_router)
router.include_router(hk_hold_router)
router.include_router(stk_surv_router)
router.include_router(report_rc_router)
router.include_router(stk_alert_router)
router.include_router(stk_shock_router)
router.include_router(ccass_hold_router)
router.include_router(ccass_hold_detail_router)
# 八、ETF/基金
router.include_router(fund_basic_router)
router.include_router(fund_daily_router)
router.include_router(fund_nav_router)
router.include_router(fund_share_router)
router.include_router(fund_portfolio_router)
router.include_router(fund_div_router)
router.include_router(fund_manager_router)
router.include_router(fund_adj_router)
router.include_router(fund_company_router)
router.include_router(fund_factor_pro_router)
router.include_router(mkt_idx_bmk_router)
router.include_router(etf_basic_router)
router.include_router(etf_index_router)
router.include_router(etf_share_size_router)
router.include_router(etf_sh_cons_router)
router.include_router(etf_sz_cons_router)
router.include_router(etf_mins_router)
router.include_router(rt_etf_k_router)
router.include_router(rt_etf_min_router)
router.include_router(rt_etf_min_daily_router)
router.include_router(rt_etf_sz_iopv_router)
router.include_router(idx_anns_router)
# 九、指数
router.include_router(index_basic_router)
router.include_router(index_daily_router)
router.include_router(index_weekly_router)
router.include_router(index_monthly_router)
router.include_router(index_weight_router)
router.include_router(index_dailybasic_router)
router.include_router(index_classify_router)
router.include_router(index_member_all_router)
router.include_router(index_global_router)
router.include_router(sw_daily_router)
router.include_router(sw_mins_router)
router.include_router(rt_sw_k_router)
router.include_router(rt_idx_k_router)
router.include_router(rt_idx_min_router)
router.include_router(idx_mins_router)
router.include_router(idx_factor_pro_router)
router.include_router(ci_daily_router)
router.include_router(ci_index_member_router)
router.include_router(daily_info_router)
router.include_router(sz_daily_info_router)
# 十、宏观/新闻/语料
router.include_router(news_router)
router.include_router(major_news_router)
router.include_router(cctv_news_router)
router.include_router(shibor_router)
router.include_router(shibor_quote_router)
router.include_router(shibor_lpr_router)
router.include_router(libor_router)
router.include_router(hibor_router)
router.include_router(gz_index_router)
router.include_router(wz_index_router)
router.include_router(cn_cpi_router)
router.include_router(cn_ppi_router)
router.include_router(cn_gdp_router)
router.include_router(cn_m_router)
router.include_router(cn_pmi_router)
router.include_router(cn_schedule_router)
router.include_router(sf_month_router)
router.include_router(eco_cal_router)
router.include_router(research_report_router)
router.include_router(anns_d_router)
router.include_router(irm_qa_sh_router)
router.include_router(irm_qa_sz_router)
router.include_router(npr_router)
router.include_router(monetary_policy_router)
router.include_router(us_tycr_router)
router.include_router(us_trltr_router)
router.include_router(us_trycr_router)
router.include_router(us_tbr_router)
router.include_router(us_tltr_router)
# 十一、债券/可转债
router.include_router(cb_basic_router)
router.include_router(cb_issue_router)
router.include_router(cb_daily_router)
router.include_router(cb_factor_pro_router)
router.include_router(cb_rating_router)
router.include_router(cb_call_router)
router.include_router(cb_share_router)
router.include_router(cb_price_chg_router)
router.include_router(cb_rate_router)
router.include_router(top10_cb_holders_router)
router.include_router(yc_cb_router)
router.include_router(repo_daily_router)
router.include_router(bond_blk_router)
router.include_router(bond_blk_detail_router)
router.include_router(bc_otcqt_router)
router.include_router(bc_bestotcqt_router)
# 十二、外汇
router.include_router(fx_obasic_router)
router.include_router(fx_daily_router)
# 十三、期权
router.include_router(opt_basic_router)
router.include_router(opt_daily_router)
router.include_router(opt_mins_router)
# 十四、期货
router.include_router(fut_basic_router)
router.include_router(fut_daily_router)
router.include_router(fut_holding_router)
router.include_router(fut_wsr_router)
router.include_router(fut_settle_router)
router.include_router(fut_weekly_detail_router)
router.include_router(fut_weekly_monthly_router)
router.include_router(fut_mapping_router)
router.include_router(fut_trade_cal_router)
router.include_router(fut_index_daily_router)
router.include_router(ft_mins_router)
router.include_router(ft_limit_router)
router.include_router(rt_fut_min_router)
# 十五、港股
router.include_router(hk_basic_router)
router.include_router(hk_tradecal_router)
router.include_router(hk_daily_router)
router.include_router(hk_daily_adj_router)
router.include_router(hk_adjfactor_router)
router.include_router(hk_mins_router)
router.include_router(hk_fina_indicator_router)
router.include_router(hk_income_router)
router.include_router(hk_balancesheet_router)
router.include_router(hk_cashflow_router)
router.include_router(rt_hk_k_router)
# 十六、美股
router.include_router(us_basic_router)
router.include_router(us_tradecal_router)
router.include_router(us_daily_router)
router.include_router(us_daily_adj_router)
router.include_router(us_adjfactor_router)
router.include_router(us_fina_indicator_router)
router.include_router(us_income_router)
router.include_router(us_balancesheet_router)
router.include_router(us_cashflow_router)
# 十七、现货
router.include_router(sge_basic_router)
router.include_router(sge_daily_router)
# 十八、自选组合
router.include_router(p_save_router)
router.include_router(p_list_router)
router.include_router(p_delete_router)
router.include_router(p_get_router)
