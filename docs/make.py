def clear(pth):
    ""
    import shutil

    try:
        shutil.rmtree(pth)
    except FileNotFoundError:
        pass


def generatedocs():
    """ """
    import os, subprocess, shutil, time

    # subprocess.check_output('pdoc controlunit -o ./docs/ --html --force')
    bpth = "./docs/controlunit"
    npth = "./docs/"
    clear(bpth)

    subprocess.check_output(f"pdoc controlunit -o ./docs/ --html --force")
    ls = os.listdir(bpth)
    ols = [os.path.join(bpth, i) for i in ls]
    nls = [os.path.join(npth, i) for i in ls]
    _ = [shutil.move(i, j) for i, j in zip(ols, nls)]
    time.sleep(0.2)
    clear(bpth)


if __name__ == "__main__":
    generatedocs()
