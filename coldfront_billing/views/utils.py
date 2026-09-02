import csv
from django.http import HttpResponse


def csv_response(data, filename="export.csv"):
    response = HttpResponse(
        content_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
    writer = csv.writer(response)
    # Write CSV header
    writer.writerow(data['header'])
    # Write CSV data row
    for row in data['rows']:
        writer.writerow(row)
    return response