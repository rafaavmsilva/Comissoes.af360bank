import multiprocessing
from system_tray import main

if __name__ == '__main__':
    # Required for Windows to handle multiprocessing properly
    multiprocessing.freeze_support()
    main()