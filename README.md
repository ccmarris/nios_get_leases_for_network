# NIOS - Database Analysis
NIOS to B1DDI Compatibility Matrix


    - Implmented silent mode (--silernt)

    - Implemented –version

    -   This reports on the version of the main script (currently named 
        main.py), the associated library and as well as version numbers for 
        the YAML config files.

        This is return as a plain dictionary (json) output to STDOUT but let 
        me know if you need headers or anything added.


Requires:

    - pandas
    - xlsxwriter
    - tqdm
    - itertools
    - collections
    - lxml
    - yaml
    - time

Basic examples::
 
    $ main.py –version
    $ main.py -d <backup_database> -c <customer_name> --silent
    $ main.py -d <database> --dump <object>
    $ main.py -d <database> --dump <object> --key_value <key> <value>


