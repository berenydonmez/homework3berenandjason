#!/bin/bash

# Define the base URL for the Flask API
BASE_URL="http://localhost:5000/api"

# Flag to control whether to echo JSON output
ECHO_JSON=false

# Parse command-line arguments
while [ "$#" -gt 0 ]; do
  case $1 in
    --echo-json) ECHO_JSON=true ;;
    *) echo "Unknown parameter passed: $1"; exit 1 ;;
  esac
  shift
done


###############################################
#
# Health checks
#
###############################################

# Function to check the health of the service
check_health() {
  echo "Checking health status..."
  curl -s -X GET "$BASE_URL/health" | grep -q '"status": "healthy"'
  if [ $? -eq 0 ]; then
    echo "Service is healthy."
  else
    echo "Health check failed."
    exit 1
  fi
}

# Function to check the database connection
check_db() {
  echo "Checking database connection..."
  curl -s -X GET "$BASE_URL/db-check" | grep -q '"database_status": "healthy"'
  if [ $? -eq 0 ]; then
    echo "Database connection is healthy."
  else
    echo "Database check failed."
    exit 1
  fi
}


##########################################################
#
# Meal Management
#
##########################################################

add_meal() {
  meal=$1
  cuisine=$2
  price=$3
  difficulty=$4

  echo "Adding meal ($meal) to the kitchen..."
  response=$(curl -s -X POST "$BASE_URL/create-meal" -H "Content-Type: application/json" \
    -d "{\"meal\":\"$meal\", \"cuisine\":\"$cuisine\", \"price\":$price, \"difficulty\":\"$difficulty\"}")

  # Check if the response contains the expected status
  echo "$response" | grep -q '"status": "combatant added"'
  if [ $? -eq 0 ]; then
    echo "Meal added successfully."
  else
    echo "Failed to add meal."
    exit 1
  fi
}

clear_catalog() {
  echo "Clearing all meals from the catalog..."
  response=$(curl -s -X DELETE "$BASE_URL/clear-meals" \
    -H "Content-Type: application/json")

  if echo "$response" | grep -q '"status": "success"'; then
    echo "Catalog cleared successfully."
    if [ "$ECHO_JSON" = true ]; then
      echo "Clear Catalog Response JSON:"
      echo "$response" | jq .
    fi
  else
    echo "Failed to clear catalog."
    echo "Response:"
    echo "$response"
    exit 1
  fi
}

delete_meal() {
  meal_id=$1

  echo "Deleting meal by ID ($meal_id)..."
  response=$(curl -s -X DELETE "$BASE_URL/delete-meal/$meal_id")
  if echo "$response" | grep -q '"status": "meal deleted"'; then
    echo "Meal deleted successfully by ID ($meal_id)."
  else
    echo "Failed to delete meal by ID ($meal_id)."
    exit 1
  fi
}

get_meal_by_id() {
  meal_id=$1

  echo "Getting meal by ID ($meal_id)..."
  response=$(curl -s -X GET "$BASE_URL/get-meal-by-id/$meal_id")
  if echo "$response" | grep -q '"status": "success"'; then
    echo "Meal retrieved successfully by ID ($meal_id)."
    if [ "$ECHO_JSON" = true ]; then
      echo "Meal JSON (ID $meal_id):"
      echo "$response" | jq .
    fi
  else
    echo "Failed to get meal by ID ($meal_id)."
    exit 1
  fi
}

get_meal_by_name() {
  name=$1

  echo "Getting meal by name ($name)..."
  response=$(curl -s -X GET "$BASE_URL/get-meal-by-name?name=$(echo $name | sed 's/ /%20/g')")
  if echo "$response" | grep -q '"status": "success"'; then
    echo "Meal retrieved successfully by name."
    if [ "$ECHO_JSON" = true ]; then
      echo "Meal JSON (by name):"
      echo "$response" | jq .
    fi
  else
    echo "Failed to get meal by name."
    exit 1
  fi
}

############################################################
#
# Battle Meal Management
#
############################################################

battle() {
  echo "Starting battle meal session..."
  response=$(curl -s -X GET "$BASE_URL/battle")

  if echo "$response" | grep -q '"status": "battle complete"'; then
    echo "Battle meal session started successfully."
  else
    echo "Failed to start battle meal session."
    exit 1
  fi
}

clear_combatants() {
  echo "Clearing all combatants from the battle..."
  response=$(curl -s -X POST "$BASE_URL/clear-combatants" \
    -H "Content-Type: application/json")

  if echo "$response" | grep -q '"status": "combatants cleared"'; then
    echo "Combatants cleared successfully."
    if [ "$ECHO_JSON" = true ]; then
      echo "Clear Combatants Response JSON:"
      echo "$response" | jq .
    fi
  else
    echo "Failed to clear combatants."
    echo "Response:"
    echo "$response"
    exit 1
  fi
}

get_combatants() {
  echo "Retrieving list of combatants..."
  response=$(curl -s -X GET "$BASE_URL/get-combatants" \
    -H "Content-Type: application/json")

  if echo "$response" | grep -q '"status": "success"'; then
    echo "Combatants retrieved successfully."
    if [ "$ECHO_JSON" = true ]; then
      echo "Get Combatants Response JSON:"
      echo "$response" | jq .
    fi
  else
    echo "Failed to retrieve combatants."
    echo "Response:"
    echo "$response"
    exit 1
  fi
}

prep_combatant() {
  meal=$1

  echo "Preparing meal '$meal' as a combatant..."
  response=$(curl -s -X POST "$BASE_URL/prep-combatant" \
    -H "Content-Type: application/json" \
    -d "{\"meal\": \"$meal\"}")

  if echo "$response" | grep -q '"status": "combatant prepared"'; then
    echo "Combatant prepared successfully."
    if [ "$ECHO_JSON" = true ]; then
      echo "Prep Combatant Response JSON:"
      echo "$response" | jq .
    fi
  elif echo "$response" | grep -q '"error": "You must name a combatant"'; then
    echo "Error: No combatant name provided."
    exit 1
  else
    echo "Failed to prepare combatant."
    echo "Response:"
    echo "$response"
    exit 1
  fi
}

get_leaderboard() {
  echo "Retrieving leaderboard sorted by wins..."
  response=$(curl -s -X GET "$BASE_URL/leaderboard" \
    -H "Content-Type: application/json")

  if echo "$response" | grep -q '"status": "success"'; then
    echo "Leaderboard retrieved successfully."
    if [ "$ECHO_JSON" = true ]; then
      echo "Leaderboard Response JSON:"
      echo "$response" | jq .
    fi
  else
    echo "Failed to retrieve leaderboard."
    echo "Response:"
    echo "$response"
    exit 1
  fi
}

############################################################
#
# Example function calls
#
############################################################

# Health checks
check_health
check_db

# Add meals
add_meal "Spaghetti Bolognese" "Italian" 12.99 "Medium"
add_meal "Pizza" "Italian" 14.99 "Medium"

# Clear the catalog (meals and other items)
clear_catalog

# Add meals
add_meal "Sushi" "Japanese" 15.99 "Hard"
add_meal "Tacos" "Mexican" 10.99 "Easy"
add_meal "Burger" "American" 8.99 "Easy"

# Delete a meal by ID (example with ID 1)
delete_meal 1

# Get meal by ID
get_meal_by_id 2

# Get meal by name
get_meal_by_name "Burger"

# Battle session
prep_combatant "Tacos"
prep_combatant "Burger"
get_combatants
battle
clear_combatants

# Leaderboard
get_leaderboard

echo "All tests passed successfully!"
