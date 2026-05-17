"""产业链定时任务测试"""

from src.scheduler.runner import create_scheduler


def test_scheduler_includes_industry_chain_job():
    scheduler = create_scheduler()
    job_ids = {job.id for job in scheduler.get_jobs()}

    assert "industry_chain_update" in job_ids
    assert "news_monitor" in job_ids
    assert "data_quality_check" in job_ids
    assert "dashboard_task_cleanup" in job_ids
    assert "weekly_report_generation" in job_ids
    assert "monthly_report_generation" in job_ids
