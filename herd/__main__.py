# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import argparse
import logging
import sys

import boto3

from herd.compat import *
from herd.serverless import Function, Region
from herd import __version__


level = logging.INFO
logging.basicConfig(format="%(message)s", level=level, stream=sys.stdout)
logger = logging.getLogger(__name__)


def main_info(args):
    r = ""
    try:
        r = Region("")
    except ValueError as e:
        pass

    logger.info("Available Regions:")
    for n in Region.names():
        if n == r:
            logger.info("\t{} (default)".format(n))
        else:
            logger.info("\t{}".format(n))
    logger.info("")

    s = boto3.Session()
    creds = s.get_credentials()
    if creds.access_key and creds.secret_key:
        logger.info("Amazon AWS access and secret keys were found")


def main_function(args):
    func = Function(
        filepath=args.filepaths[0],
        role_name=args.role_name,
        api_name=args.api_name,
        stage=args.stage,
        region_name=args.region_name
    )

    logger.info("Function {} available at url: {}".format(func.func.name, func.url))


def main():
    parser = argparse.ArgumentParser(description='Herd - Manage AWS things')
    parser.add_argument("--version", "-V", "-v", action='version', version="%(prog)s {}".format(__version__))
    parser.add_argument("--debug", "-d", action="store_true", help="More verbose logging")

    # some parsers can take an input string, this is the common argument for them
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--debug", "-d", action="store_true", help="More verbose output")

    subparsers = parser.add_subparsers(dest="command", help="a sub command")
    subparsers.required = True # https://bugs.python.org/issue9253#msg186387

    # $ herd info
    desc = "Get info about the environment"
    subparser = subparsers.add_parser(
        "info",
        parents=[common_parser],
        help=desc,
        description=desc,
        conflict_handler="resolve",
    )
    subparser.set_defaults(func=main_info)

    # $ herd function
    desc = "Add lambda function"
    subparser = subparsers.add_parser(
        "function-add",
        parents=[common_parser],
        help=desc,
        description=desc,
        conflict_handler="resolve",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparser.add_argument(
        "--role-name",
        help="The name of the AWS IAM role to use for the lambda and api",
        default="herd-lambda-role",
    )
    subparser.add_argument(
        "--api-name",
        help="The name/id of the AWS api gateway",
        default="herd-lambda-api",
    )
    subparser.add_argument(
        "--stage", "-s",
        help="The staging environment name (eg, DEV, STAGING, PROD)",
        default="herd-lambda-api",
    )
    subparser.add_argument(
        "--region-name",
        help="The AWS region",
        default="",
    )
    subparser.add_argument(
        "filepaths",
        nargs=1,
        metavar="FILEPATH",
        help="The path to a module.py that contains a NAME(event, context) function",
    )
    subparser.set_defaults(func=main_function)

    args = parser.parse_args()

    # mess with logging
    if args.debug:
        logger.setLevel(logging.DEBUG)

    code = args.func(args)
    sys.exit(code)


if __name__ == "__main__":
    main()

