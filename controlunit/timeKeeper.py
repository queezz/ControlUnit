from datetime import datetime
import logging
from logging import getLogger, StreamHandler, Formatter

def time_keeper():
    now = datetime.now()
    formatter = Formatter('%(asctime)s:%(levelname)s:%(message)s')
    logging.basicConfig(filename="data/log/{:%Y%m%d%H%M%S}.log".format(now), level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')
    logger = logging.getLogger("{:%Y%m%d%H%M%S}".format(now))

    help()
    while(True):
        an = input("input command: ")
        if an[:3] == "pon":
            t = datetime.now()
            logger.info("{} plasma start".format(an[4:]))
            print("{} plasma start time: {}".format(an[4:], t))
        elif an == "poff":
            t = datetime.now()
            logger.info("plasma stop")
            print("plasma stop time: {}".format(t))
        elif an[:3] == "gin":
            t = datetime.now()
            logger.info("{} gas inflow start time".format(an[4:]))
            print("{} gas inflow start time: {}".format(an[4:], t))
        elif an[:4] == "gout":
            t = datetime.now()
            logger.info("{} gas inflow stop time".format(an[5:]))
            print("{} gas inflow stop time: {}".format(an[5:], t))
        elif an == "vgopen":
            t = datetime.now()
            logger.info("connect membrane chamber and plasma chamber")
            print("connect membrane chamber and plasma chamber: {}".format(t))
        elif an == "vgclose":
            t = datetime.now()
            logger.info("disconnect membrane chamber and plasma chamber")
            print("disconnect membrane chamber and plasma chamber: {}".format(t))
        elif an == "-h" or an == "--help" or an == "help":
            help()
        elif an == "exit" or an == "exit()":
            t = datetime.now()
            print("exit: {}".format(t))
            break
        else:
            t = datetime.now()
            logger.info("{}".format(an))
            print("{} : {}".format(an, t))
        print("")

def help():
    print("")
    print("-------time keeper--------")
    print("help:")
    print("     `pon {ampere}`: plasma on time")
    print("     `poff`: plasma off time")
    print("     `gin {gas_name}`: gas inflow start time")
    print("     `gout {gas_name}`: gas inflow stop time")
    print("     `vgopen`: connect membrane chamber and plasma chamber")
    print("     `vgclose`: disconnect membrane chamber and plasma chamber")
    print("     `exit`: exit from this problem")
    print("     `help`: show help")
    print("")
    print("example: ")
    print("     `$ input command: pon`")
    print("     `$ plasma start time: 2019-12-27 17:05:37.226898`")
    print("----------------------------")
    print("")

if __name__ == "__main__":
    time_keeper()
