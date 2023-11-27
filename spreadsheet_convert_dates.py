import csv
from datetime import datetime

input_file = "Joe - Streams.tsv"
output_file = "streamdates.tsv"

with open(input_file, "r", newline="") as in_file, open(output_file, "w", newline="") as out_file:
    tsv_reader = csv.reader(in_file, delimiter="\t")
    tsv_writer = csv.writer(out_file, delimiter="\t")

    last_date = None

    for row in tsv_reader:
        if not row[0]:
            continue
        if len(row) >= 3:
            date_str = row[1]
            try:
                # convert the date to the "yyyy-mm-dd" format
                date_obj = datetime.strptime(date_str, "%a, %m/%d/%Y")
                formatted_date = date_obj.strftime("%Y-%m-%d")
                row[1] = formatted_date
                last_date = formatted_date
                tsv_writer.writerow(row)
            except ValueError:
                print(f"Invalid date format in row: {row}")
                if last_date:
                    row[1] = last_date
                    tsv_writer.writerow(row)
                else:
                    # if there's no last date, write the row as-is
                    tsv_writer.writerow(row)
        else:
            if last_date:
                row = [row[0]] + [last_date] + row[2:]  # insert the last date into the row
                tsv_writer.writerow(row)
            else:
                # write rows without the expected format as-is
                tsv_writer.writerow(row)

print(f"Conversion completed. Output written to '{output_file}'.")
