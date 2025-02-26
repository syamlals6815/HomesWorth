
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
import joblib

# Load dataset
data = pd.read_csv("predictor/static/house_price_data_cochin2.csv")

# Preprocess data
X = data[["location", "area_in_sq_ft", "bedrooms", "bathrooms", "age_of_home", "parking_slot"]]
y = data["price"]
X = pd.get_dummies(X, columns=["location"], drop_first=True)

# Save the list of column names
expected_columns = X.columns.tolist()
joblib.dump(expected_columns, "predictor/ml_models/expected_columns.pkl")

# Split the data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train the model
model = LinearRegression()
model.fit(X_train, y_train)

# Save the trained model
joblib.dump(model, "predictor/ml_models/trained_model.pkl")
print("Model and expected columns saved successfully!")
