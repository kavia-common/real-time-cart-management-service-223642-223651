#!/bin/bash
cd /home/kavia/workspace/code-generation/real-time-cart-management-service-223642-223651/lambda_cart_manager
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

