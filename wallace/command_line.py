#!/usr/bin/python
# -*- coding: utf-8 -*-

import optparse
import uuid
import os
import shutil
from psiturk.psiturk_config import PsiturkConfig
import subprocess
import time


def log(msg, delay=0.5, chevrons=True):
    if chevrons:
        print "\n❯❯ " + msg
    else:
        print msg
    time.sleep(delay)


def main():
    """A command line interface for Wallace."""
    p = optparse.OptionParser()
    p.add_option("--debug", action="callback", callback=deploy)
    p.add_option("--deploy", action="callback", callback=deploy)

    options, arguments = p.parse_args()


def deploy(*args):
    """Deploy app to psiTurk."""

    # Generate a unique id for this experiment.
    id = "w" + str(uuid.uuid4())[0:18]
    log("Deploying as experiment " + id + ".")

    # Load psiTurk configuration.
    config = PsiturkConfig()
    config.load_config()

    # Create a git repository if one does not already exist.
    if not os.path.exists(".git"):
        log("No git repository detected; creating one.")
        cmds = ["git init",
                "git add .",
                'git commit -m "Experiment ' + id + '"']
        for cmd in cmds:
            subprocess.call(cmd, shell=True)
            time.sleep(0.5)

    # Create a new branch.
    log("Creating new branch and switching over to it...")
    subprocess.call("git branch " + id, shell=True)
    time.sleep(1)
    subprocess.call("git checkout " + id, shell=True)

    # Copy custom.py into this experiment package.
    src = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "custom.py")
    dst = os.path.join(os.getcwd(), "custom.py")
    shutil.copy(src, dst)

    # Copy the Procfile into this experiment package.
    src = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "heroku",
        "Procfile")
    dst = os.path.join(os.getcwd(), "Procfile")
    shutil.copy(src, dst)

    # Copy the requirements.txt file into this experiment package.
    src = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "heroku",
        "requirements.txt")
    dst = os.path.join(os.getcwd(), "requirements.txt")
    shutil.copy(src, dst)

    # Create the psiturk command script.
    with open("psiturk_commands.txt", "w") as file:
        file.write("server on")

    # Commit the new files to the new experiment branch.
    log("Inserting psiTurk- and Heroku-specfic files.")
    subprocess.call("git add .", shell=True),
    time.sleep(0.25)
    subprocess.call(
        'git commit -m "Inserting psiTurk- and Heroku-specfic files"',
        shell=True)
    time.sleep(0.25)

    # Initialize the app on Heroku.
    log("Initializing app on Heroku...")
    subprocess.call(
        "heroku apps:create " + id +
        " --buildpack https://github.com/thenovices/heroku-buildpack-scipy",
        shell=True)

    # Set up postgres database and AWS/psiTurk environment variables.
    cmds = [
        "heroku addons:add heroku-postgresql:hobby-dev",
        "heroku pg:wait",
        "heroku config:set aws_access_key_id=" + config.get('AWS Access', 'aws_access_key_id'),
        "heroku config:set aws_secret_access_key=" + config.get('AWS Access', 'aws_secret_access_key'),
        "heroku config:set aws_region=" + config.get('AWS Access', 'aws_region'),
        "heroku config:set psiturk_access_key_id=" + config.get('psiTurk Access', 'psiturk_access_key_id'),
        "heroku config:set psiturk_secret_access_id=" + config.get('psiTurk Access', 'psiturk_secret_access_id')
    ]
    for cmd in cmds:
        subprocess.call(cmd + " --app " + id, shell=True)

    # Launch the Heroku app.
    subprocess.call("git push heroku " + id + ":master", shell=True)

    # Send launch signal to server.
    host = config.get('Server Parameters', 'host')
    port = config.get('Server Parameters', 'port')
    url = "http://" + host + ":" + port + "/launch"
    # print pexpect.run("curl -X POST " + url)


def debug(*args):
    """Run the experiment locally."""
    raise NotImplementedError

if __name__ == "__main__":
    main()

log("""
     _    _    __    __    __      __    ___  ____
    ( \/\/ )  /__\  (  )  (  )    /__\  / __)( ___)
     )    (  /(__)\  )(__  )(__  /(__)\( (__  )__)
    (__/\__)(__)(__)(____)(____)(__)(__)\___)(____)

             a platform for experimental evolution.

""", 0.5, False)
