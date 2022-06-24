from project.extensions import scheduler

scheduler.delete_all_jobs()
from project.jobs import data_job
from project.jobs import calculate_job
from project.jobs import earnings_pr_job
from project.jobs import earnings_pledge_job
from project.jobs import earnings_trans_job
from project.jobs import earnings_top_nodes_job
from project.jobs import liquidity_events_job
from project.jobs import binance_pledge_events_job
from project.jobs import matic_pledge_events_job
from project.jobs import prefetching_event_job
from project.jobs import prefetching_chain_job
from project.jobs import del_old_datas_job
from project.jobs import reset_time_job