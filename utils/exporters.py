import csv
from django.http import HttpResponse

def export_report_to_csv(report_data):
    """
    خروجی فایل CSV فارسی و استاندارد از گزارش مالی دوره‌ای.
    """
    from utils.jalali import jalali_str
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="financial_report.csv"'
    
    # افزودن BOM برای نمایش صحیح کاراکترهای فارسی در اکسل
    response.write("\ufeff".encode("utf-8"))
    
    writer = csv.writer(response)
    writer.writerow(["شاخص مالی", "مقدار (تومان)"])
    writer.writerow(["درآمد ناخالص فاکتورها", int(report_data["total_revenue"])])
    writer.writerow(["مجموع خرید مواد اولیه انبار", int(report_data["purchases_sum"])])
    writer.writerow(["مجموع هزینه‌های عملیاتی پروژه‌ها", int(report_data["operational_costs_sum"])])
    writer.writerow(["کل هزینه‌ها", int(report_data["total_expenses"])])
    writer.writerow(["کل دریافتی‌های تاییدشده", int(report_data["total_received"])])
    writer.writerow(["تفاضل نهایی (درآمد منهای هزینه)", int(report_data["net_difference"])])
    
    return response
