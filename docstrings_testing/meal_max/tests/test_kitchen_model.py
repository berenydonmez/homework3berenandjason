import os
from contextlib import contextmanager
import re
import sqlite3

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

    # Mock the connection's cursor
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None  # Default return for queries
    mock_cursor.fetchall.return_value = []
    mock_cursor.commit.return_value = None

    # Mock the get_db_connection context manager from sql_utils
    @contextmanager
    def mock_get_db_connection():
        yield mock_conn  # Yield the mocked connection object

    mocker.patch('meal_max.models.kitchen_model.get_db_connection', mock_get_db_connection)

    return mock_cursor  # Return the mock cursor so we can set expectations per test

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

##################################################
# Clear Meals Test Cases
##################################################

def test_clear_meals(mock_cursor, sample_meal1):
    """Test clearing all meals from the database."""
    create_meal(sample_meal1.meal, sample_meal1.cuisine, 
                sample_meal1.price, sample_meal1.difficulty)
    
    clear_meals()
    
    mock_cursor.execute.assert_called_with("SELECT COUNT(*) FROM meals")
    mock_cursor.fetchone.return_value = (0,)
    assert mock_cursor.fetchone()[0] == 0, "Database should be empty after clearing"

def test_clear_meals_empty_database(mock_cursor, caplog):
    """Test clearing meals when database is already empty."""
    mock_cursor.execute.return_value = None
    mock_cursor.fetchone.return_value = (0,)
    
    clear_meals()
    
    assert "No meals found to clear" in caplog.text, "Expected warning when clearing empty database"
    
    mock_cursor.execute.assert_called_with("SELECT COUNT(*) FROM meals")
    assert mock_cursor.fetchone()[0] == 0, "Database should still be empty"
    
##################################################
# Meal Retrieval Test Cases
##################################################

def test_get_meal_by_id_success(mock_cursor, sample_meal1):
    """Test successful meal retrieval by ID."""
    mock_cursor.fetchone.return_value = (1, "Manti", "Turkish", 12.99, "MED", False)
    
    meal = get_meal_by_id(1)
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

def test_get_meal_by_name_success(mock_cursor, sample_meal1):
    """Test successful meal retrieval by name."""
    mock_cursor.fetchone.return_value = (1, "Manti", "Turkish", 12.99, "MED", False)
    
    meal = get_meal_by_name("Manti")
    assert meal.meal == "Manti"
    assert meal.cuisine == "Turkish"

##################################################
# Meal Deletion Test Cases
##################################################

def test_delete_meal_success(mock_cursor):
    """Test successful meal deletion."""
    mock_cursor.fetchone.return_value = (False,)
    
    delete_meal(1)
    assert "UPDATE meals SET deleted = TRUE" in mock_cursor.execute.call_args_list[-1][0][0]

def test_delete_already_deleted_meal(mock_cursor):
    """Test error when deleting an already deleted meal."""
    mock_cursor.fetchone.return_value = (True,)
    
    with pytest.raises(ValueError, match="Meal with ID 1 has been deleted"):
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

def test_update_meal_stats_invalid_result(mock_cursor):
    """Test error when updating stats with invalid result."""
    mock_cursor.fetchone.return_value = (False,)
    
    with pytest.raises(ValueError, match="Invalid result: draw"):
        update_meal_stats(1, 'draw')

##################################################
# Leaderboard Test Cases
##################################################

def test_get_leaderboard_by_wins(mock_cursor):
    """Test retrieving leaderboard sorted by wins."""
    mock_cursor.fetchall.return_value = [
        (1, "Manti", "Turkish", 12.99, "MED", 10, 8, 0.8),
        (2, "Sushi", "Japanese", 15.99, "HIGH", 8, 6, 0.75)
    ]
    
    leaderboard = get_leaderboard("wins")
    assert len(leaderboard) == 2
    assert leaderboard[0]['wins'] == 8
    assert leaderboard[0]['win_pct'] == 80.0

def test_get_leaderboard_invalid_sort(mock_cursor):
    """Test error when getting leaderboard with invalid sort parameter."""
    with pytest.raises(ValueError, match="Invalid sort_by parameter: invalid"):
        get_leaderboard("invalid")
