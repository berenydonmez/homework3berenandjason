import os
from contextlib import contextmanager
import re
import sqlite3
from unittest.mock import mock_open, patch

import pytest

import meal_max
from meal_max.models.kitchen_model import (
    Meal, 
    create_meal, 
    get_meal_by_id, 
    get_meal_by_name, 
    delete_meal, 
    update_meal_stats, 
    get_leaderboard,
    clear_meals
)

from meal_max.utils.sql_utils import get_db_connection
from meal_max.utils.logger import configure_logger

######################################################
#
#    Fixtures
#
######################################################

@pytest.fixture
def sample_meal1():
    """Fixture providing a sample meal for testing."""
    return Meal(
        id=1,
        meal="Manti",
        cuisine="Turkish",
        price=12.99,
        difficulty="MED"
    )

@pytest.fixture
def sample_meal2():
    """Fixture providing another sample meal for testing."""
    return Meal(
        id=2,
        meal="Sushi Roll",
        cuisine="Japanese",
        price=15.99,
        difficulty="HIGH"
    )

@pytest.fixture
def mock_cursor(mocker):
    mock_conn = mocker.Mock()
    mock_cursor = mocker.Mock()

    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    mock_cursor.commit.return_value = None

    @contextmanager
    def mock_get_db_connection():
        yield mock_conn

    mocker.patch('meal_max.models.kitchen_model.get_db_connection', mock_get_db_connection)

    return mock_cursor

##################################################
# Attribute Validation Test Cases
##################################################

def test_valid_price_and_difficulty():
    """Test that valid price and difficulty values do not raise an error."""
    meal = Meal(id=1, meal="Pasta", cuisine="Italian", price=10.99, difficulty="MED")
    assert meal.price == 10.99
    assert meal.difficulty == "MED"

def test_negative_price_raises_value_error():
    """Test that a negative price raises a ValueError."""
    with pytest.raises(ValueError, match="Price must be a positive value."):
        Meal(id=2, meal="Salad", cuisine="French", price=-5.00, difficulty="LOW")

def test_invalid_difficulty_raises_value_error():
    """Test that an invalid difficulty level raises a ValueError."""
    with pytest.raises(ValueError, match="Difficulty must be 'LOW', 'MED', or 'HIGH'."):
        Meal(id=4, meal="Burger", cuisine="American", price=8.99, difficulty="MEDIUM")

##################################################
# Meal Creation Test Cases
##################################################

def test_create_meal_success(mock_cursor):
    """Test successful meal creation."""
    create_meal("Manti", "Turkish", 12.99, "MED")
    
    mock_cursor.execute.assert_called_once()
    assert "INSERT INTO meals" in mock_cursor.execute.call_args[0][0]

def test_create_meal_invalid_price():
    """Test error when creating meal with invalid price."""
    with pytest.raises(ValueError, match="Invalid price: -5. Price must be a positive number"):
        create_meal("Manti", "Turkish", -5, "MED")

def test_create_meal_invalid_difficulty():
    """Test error when creating meal with invalid difficulty level."""
    with pytest.raises(ValueError, match="Invalid difficulty level: EXTREME"):
        create_meal("Manti", "Turkish", 12.99, "EXTREME")

def test_create_duplicate_meal(mock_cursor):
    """Test error when creating a duplicate meal."""
    mock_cursor.execute.side_effect = sqlite3.IntegrityError
    
    with pytest.raises(ValueError, match="Meal with name 'Manti' already exists"):
        create_meal("Manti", "Turkish", 12.99, "MED")

def test_create_meal_database_error(mock_cursor):
    """Test that a database error raises an sqlite3.Error."""
    mock_cursor.execute.side_effect = sqlite3.Error("Database error")

    with pytest.raises(sqlite3.Error, match="Database error"):
        create_meal("Pasta", "Italian", 10.99, "MED")

##################################################
# Clear Meals Test Case
##################################################

def test_clear_meals(mock_cursor, mocker):
    """Test clearing all meals from the database."""
    mock_create_table_script = """
    DROP TABLE IF EXISTS meals;
    CREATE TABLE meals (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        cuisine TEXT NOT NULL,
        price REAL NOT NULL,
        difficulty TEXT NOT NULL,
        deleted BOOLEAN DEFAULT FALSE,
        battles INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0
    );
    """
    
    mock_file = mocker.mock_open(read_data=mock_create_table_script)
    mocker.patch("builtins.open", mock_file)
    
    clear_meals()
    
    mock_cursor.executescript.assert_called_once_with(mock_create_table_script)
    assert mock_cursor.connection.commit.call_count == 0

def test_clear_meals_empty_database(mock_cursor, mocker, caplog):
    """Test clearing meals when database is empty."""
    mock_create_table_script = """
    DROP TABLE IF EXISTS meals;
    CREATE TABLE meals (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        cuisine TEXT NOT NULL,
        price REAL NOT NULL,
        difficulty TEXT NOT NULL,
        deleted BOOLEAN DEFAULT FALSE,
        battles INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0
    );
    """
    
    mock_file = mocker.mock_open(read_data=mock_create_table_script)
    mocker.patch("builtins.open", mock_file)
    
    mock_cursor.fetchall.return_value = []
    
    clear_meals()
    
    mock_cursor.executescript.assert_called_once_with(mock_create_table_script)
    assert mock_cursor.connection.commit.call_count == 0
    assert "Meals cleared successfully." in caplog.text

def test_clear_meals_database_error(mock_cursor):
    """Test that a database error raises an sqlite3.Error when clearing meals."""
    mock_open_data = "CREATE TABLE meals (id INTEGER PRIMARY KEY);"
    
    with patch('builtins.open', mock_open(read_data=mock_open_data)):
        mock_cursor.executescript.side_effect = sqlite3.Error("Database error")

        with pytest.raises(sqlite3.Error, match="Database error"):
            clear_meals()

##################################################
# Meal Retrieval Test Cases
##################################################

def test_get_meal_by_id_success(mock_cursor, sample_meal1):
    """Test successful meal retrieval by ID."""
    mock_cursor.fetchone.return_value = (1, "Manti", "Turkish", 12.99, "MED", False)
    
    meal = get_meal_by_id(1)
    assert meal.id == 1
    assert meal.meal == "Manti"
    assert meal.cuisine == "Turkish"
    assert meal.price == 12.99
    assert meal.difficulty == "MED"

def test_get_meal_by_id_not_found(mock_cursor):
    """Test error when getting non-existent meal by ID."""
    mock_cursor = mock_cursor().cursor()
    mock_cursor.fetchone.return_value = None
    
    with pytest.raises(ValueError, match="Meal with ID 999 not found"):
        get_meal_by_id(999)

def test_get_meal_by_id_deleted(mock_cursor):
    """Test retrieval of a meal that has been marked as deleted."""
    mock_cursor.fetchone.return_value = (1, "Manti", "Turkish", 12.99, "MED", True)

    with pytest.raises(ValueError, match="Meal with ID 1 has been deleted"):
        get_meal_by_id(1)

def test_get_meal_by_id_database_error(mocker):
    """Test handling of a database error during meal retrieval."""
    mock_conn = mocker.Mock()
    mock_cursor = mocker.Mock()

    mock_conn.cursor.return_value = mock_cursor

    @contextmanager
    def mock_get_db_connection():
        yield mock_conn

    mocker.patch('meal_max.models.kitchen_model.get_db_connection', mock_get_db_connection)

    mock_cursor.execute.side_effect = sqlite3.Error("Database error")

    with pytest.raises(sqlite3.Error, match="Database error"):
        get_meal_by_id(1)

def test_get_meal_by_name_success(mock_cursor, sample_meal1):
    """Test successful meal retrieval by name."""
    mock_cursor.fetchone.return_value = (1, "Manti", "Turkish", 12.99, "MED", False)

    meal = get_meal_by_name("Manti")
    
    assert meal.id == 1
    assert meal.meal == "Manti"
    assert meal.cuisine == "Turkish"
    assert meal.price == 12.99
    assert meal.difficulty == "MED"


def test_get_meal_by_name_not_found(mock_cursor):
    """Test error when getting a non-existent meal by name."""
    mock_cursor.fetchone.return_value = None

    with pytest.raises(ValueError, match="Meal with name Pizza not found"):
        get_meal_by_name("Pizza")


def test_get_meal_by_name_deleted(mock_cursor):
    """Test retrieval of a meal that has been marked as deleted."""
    mock_cursor.fetchone.return_value = (1, "Manti", "Turkish", 12.99, "MED", True)

    with pytest.raises(ValueError, match="Meal with name Manti has been deleted"):
        get_meal_by_name("Manti")


def test_get_meal_by_name_database_error(mocker):
    """Test handling of a database error during meal retrieval."""
    mock_conn = mocker.Mock()
    mock_cursor = mocker.Mock()

    mock_conn.cursor.return_value = mock_cursor

    @contextmanager
    def mock_get_db_connection():
        yield mock_conn

    mocker.patch('meal_max.models.kitchen_model.get_db_connection', mock_get_db_connection)

    mock_cursor.execute.side_effect = sqlite3.Error("Database error")

    with pytest.raises(sqlite3.Error, match="Database error"):
        get_meal_by_name("Manti")

##################################################
# Meal Deletion Test Cases
##################################################

def test_delete_meal_success(mock_cursor):
    """Test successful meal deletion."""
    mock_cursor.fetchone.return_value = (False,)
    
    delete_meal(1)
    assert "UPDATE meals SET deleted = TRUE" in mock_cursor.execute.call_args_list[-1][0][0]

def test_delete_meal_not_found(mock_cursor):
    """Test error when trying to delete a meal that does not exist."""
    mock_cursor.fetchone.return_value = None
    
    with pytest.raises(ValueError, match="Meal with ID 1 not found"):
        delete_meal(1)

def test_delete_already_deleted_meal(mock_cursor):
    """Test error when deleting an already deleted meal."""
    mock_cursor.fetchone.return_value = (True,)
    
    with pytest.raises(ValueError, match="Meal with ID 1 has been deleted"):
        delete_meal(1)

def test_delete_meal_database_error(mock_cursor):
    """Test that a database error raises sqlite3.Error when deleting a meal."""
    mock_cursor.fetchone.return_value = (False,)

    mock_cursor.execute.side_effect = sqlite3.Error("Database error")

    with pytest.raises(sqlite3.Error, match="Database error"):
        delete_meal(1)

##################################################
# Battle Statistics Test Cases
##################################################

def test_update_meal_stats_win(mock_cursor):
    """Test updating meal stats for a win."""
    mock_cursor.fetchone.return_value = (False,)
    
    update_meal_stats(1, 'win')
    assert "UPDATE meals SET battles = battles + 1, wins = wins + 1" in mock_cursor.execute.call_args_list[-1][0][0]

def test_update_meal_stats_loss(mock_cursor):
    """Test updating meal stats for a loss."""
    mock_cursor.fetchone.return_value = (False,)
    
    update_meal_stats(1, 'loss')
    assert "UPDATE meals SET battles = battles + 1" in mock_cursor.execute.call_args_list[-1][0][0]

def test_update_meal_stats_not_found(mock_cursor):
    """Test error when trying to update a non-existent meal."""
    mock_cursor.fetchone.side_effect = TypeError

    with pytest.raises(ValueError, match="Meal with ID 999 not found"):
        update_meal_stats(999, 'win')


def test_update_meal_stats_deleted(mock_cursor):
    """Test retrieval of a meal that has been marked as deleted."""
    mock_cursor.fetchone.return_value = (True,)

    with pytest.raises(ValueError, match="Meal with ID 1 has been deleted"):
        update_meal_stats(1, 'win')


def test_update_meal_stats_invalid_result(mock_cursor):
    """Test error when an invalid result is provided."""
    mock_cursor.fetchone.return_value = (False,)

    with pytest.raises(ValueError, match="Invalid result: invalid_result. Expected 'win' or 'loss'."):
        update_meal_stats(1, 'invalid_result')


def test_update_meal_stats_database_error(mocker):
    """Test handling of a database error during the update process."""
    mock_conn = mocker.Mock()
    mock_cursor = mocker.Mock()

    mock_conn.cursor.return_value = mock_cursor

    @contextmanager
    def mock_get_db_connection():
        yield mock_conn

    mocker.patch('meal_max.models.kitchen_model.get_db_connection', mock_get_db_connection)

    mock_cursor.execute.side_effect = sqlite3.Error("Database error")

    with pytest.raises(sqlite3.Error, match="Database error"):
        update_meal_stats(1, 'win')

##################################################
# Leaderboard Test Cases
##################################################

def test_get_leaderboard_sorted_by_wins(mock_cursor):
    """Test retrieving the leaderboard sorted by wins."""
    mock_cursor.fetchall.return_value = [
        (1, "Pasta", "Italian", 10.99, "MED", 5, 4, 0.8),
        (2, "Sushi", "Japanese", 15.99, "HIGH", 3, 3, 1.0)
    ]
    
    leaderboard = get_leaderboard("wins")
    
    assert len(leaderboard) == 2
    assert leaderboard[0]['meal'] == "Pasta"
    assert leaderboard[1]['meal'] == "Sushi"
    assert leaderboard[0]['wins'] == 4
    assert leaderboard[1]['wins'] == 3

def test_get_leaderboard_sorted_by_win_pct(mock_cursor):
    """Test retrieving the leaderboard sorted by win percentage."""
    mock_cursor.fetchall.return_value = [
        (1, "Pasta", "Italian", 10.99, "MED", 5, 4, 0.8),
        (2, "Sushi", "Japanese", 15.99, "HIGH", 3, 3, 1.0)
    ]
    
    leaderboard = get_leaderboard("win_pct")
    
    assert len(leaderboard) == 2
    assert leaderboard[0]['meal'] == "Pasta"
    assert leaderboard[1]['meal'] == "Sushi"
    assert leaderboard[0]['win_pct'] == 80.0
    assert leaderboard[1]['win_pct'] == 100.0

def test_get_leaderboard_sorted_by_wins(mock_cursor):
    """Test that the leaderboard is returned correctly when sorted by wins."""
    mock_cursor.fetchall.return_value = [
        (1, 'Meal 1', 'Italian', 10.0, 'Easy', 5, 3, 0.6),
        (2, 'Meal 2', 'Mexican', 12.0, 'Medium', 8, 5, 0.625),
        (3, 'Meal 3', 'Chinese', 15.0, 'Hard', 10, 7, 0.7)
    ]

    expected_leaderboard = [
        {'id': 1, 'meal': 'Meal 1', 'cuisine': 'Italian', 'price': 10.0, 'difficulty': 'Easy', 'battles': 5, 'wins': 3, 'win_pct': 60.0},
        {'id': 2, 'meal': 'Meal 2', 'cuisine': 'Mexican', 'price': 12.0, 'difficulty': 'Medium', 'battles': 8, 'wins': 5, 'win_pct': 62.5},
        {'id': 3, 'meal': 'Meal 3', 'cuisine': 'Chinese', 'price': 15.0, 'difficulty': 'Hard', 'battles': 10, 'wins': 7, 'win_pct': 70.0}
    ]

    leaderboard = get_leaderboard(sort_by="wins")

    assert leaderboard == expected_leaderboard

def test_get_leaderboard_sorted_by_win_pct(mock_cursor):
    """Test that the leaderboard is returned correctly when sorted by win percentage."""
    mock_cursor.fetchall.return_value = [
        (1, 'Meal 1', 'Italian', 10.0, 'Easy', 5, 3, 0.6),
        (2, 'Meal 2', 'Mexican', 12.0, 'Medium', 8, 5, 0.625),
        (3, 'Meal 3', 'Chinese', 15.0, 'Hard', 10, 7, 0.7)
    ]

    expected_leaderboard = [
        {'id': 1, 'meal': 'Meal 1', 'cuisine': 'Italian', 'price': 10.0, 'difficulty': 'Easy', 'battles': 5, 'wins': 3, 'win_pct': 60.0},
        {'id': 2, 'meal': 'Meal 2', 'cuisine': 'Mexican', 'price': 12.0, 'difficulty': 'Medium', 'battles': 8, 'wins': 5, 'win_pct': 62.5},
        {'id': 3, 'meal': 'Meal 3', 'cuisine': 'Chinese', 'price': 15.0, 'difficulty': 'Hard', 'battles': 10, 'wins': 7, 'win_pct': 70.0}
    ]

    leaderboard = get_leaderboard(sort_by="win_pct")

    assert leaderboard == expected_leaderboard

def test_get_leaderboard_invalid_sort(mock_cursor):
    """Test error when getting leaderboard with invalid sort parameter."""
    with pytest.raises(ValueError, match="Invalid sort_by parameter: invalid"):
        get_leaderboard("invalid")

def test_get_leaderboard_database_error(mock_cursor):
    """Test that a database error raises an sqlite3.Error."""
    mock_cursor.fetchall.side_effect = sqlite3.Error("Database error")
    
    with pytest.raises(sqlite3.Error, match="Database error"):
        get_leaderboard("wins")
