class xps_dummy:
    @staticmethod
    def get_model_type(sock):
        return "C"

    def ftp_cli(self):
        pass

class dummy_child(xps_dummy):

    def ftp_cli(self):
        print("I am C")


class xps_maker:

    make_xps(sock):
    # use
    version to make = xps_dummy.get_model_type(sock):

    return version()