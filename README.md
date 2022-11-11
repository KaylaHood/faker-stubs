# faker-stubs
Quick and dirty script to generate faker stubs for Faker 15.1.1

# Prerequisites
- You must have Faker installed *(this has been tested with Faker 15.1.1 but it probably works for other versions as well)*
- Your Python version must be 3.9 *(I have not tested this script on any other version)*

# To install
This isn't hosted on pypi or any other python package sharing site, so you'll need to install this manually if you're really determined to get autocompletion for Faker.
Luckily, the installation is pretty straightforward. Here are the steps:
1. Read the Prerequisites section and make sure your environment satisfies all of them.
2. Download generate_stub.py and save it anywhere on your machine. If you ever update the faker library you'll need to run it again, so keep it somewhere you'll remember.
3. Run the file *(you can do this however you'd like, but I've included the steps for the most common method below)*
    1. For unix/macOS: Open a terminal session and run the following commands
        ```
        cd ${directory_where_you_saved_generate_stub}
        python ./generate_stub.py
        ```  
        (`${directory_where_you_saved_generate_stub}` *should be replaced with the POSIX-style path to the directory where you saved generate_stub.py)*
    2. For windows: Open a command prompt session and run the following commands
        ```
        cd %DIRECTORY_WHERE_YOU_SAVED_GENERATE_STUB%
        python .\generate_stub.py
        ```  
        (`%DIRECTORY_WHERE_YOU_SAVED_GENERATE_STUB%` *should be replaced with the Windows-style path to the directory where you saved generate_stub.py)*
4. Open your favorite IDE and try auto-completion on a Faker instance, all of the provider methods (for all locales) should be included in the drop-down!

# Notes
- ALL locales' provider methods (including the default locale) are included in the stub. This means that some of the methods in your auto-completion might not actually be present in your Faker instance if you selected a specific locale which doesn't contain the method you want to use.  
    If you create your faker instance using the normal initialization method with no locale arguments (i.e. `faker.Faker()`) then you don't need to worry about this; all of the methods in the auto-completion dropdown will be available to your instance.