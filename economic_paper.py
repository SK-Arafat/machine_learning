import matplotlib.pyplot as plt
import numpy as np

plt.style.use('ggplot')

# Graphic 1: Tariff and Currency Offset
def plot_tariff_offset():
    base_price, tariff_rate, currency_offset = 100, 0.10, 0.10
    prices = [base_price, base_price * (1 + tariff_rate), 
              base_price * (1 - currency_offset) * (1 + tariff_rate)]
    labels = ['No Tariff', 'Tariff, No Offset', 'Tariff with Offset']
    
    plt.figure(figsize=(8, 6))
    bars = plt.bar(labels, prices, color=['#4CAF50', '#FF5733', '#3498DB'], edgecolor='black')
    plt.title('Impact of Tariffs on Import Prices\n(10% Tariff on $100 Widget)', fontsize=14)
    plt.ylabel('Price in USD', fontsize=12)
    plt.ylim(0, 120)
    for bar in bars:
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, f'${bar.get_height():.2f}', 
                 ha='center', va='bottom', fontsize=10)
    plt.text(0.5, 0.95, 'Currency Offset Reduces Price Impact\n(2018-2019 Example)', 
             transform=plt.gca().transAxes, fontsize=10, ha='center', bbox=dict(facecolor='white', alpha=0.8))
    plt.tight_layout()
    plt.savefig('tariff_offset.png')
    plt.show()

# Graphic 2: Stock Market Scenarios (Updated with Steps vs. No Steps)
def plot_stock_scenarios():
    time = np.arange(1, 6)  # April to August
    baseline = 507.075  # Today’s SPY close
    steps_taken = baseline * (1 + np.linspace(0, 0.10, 5))  # +10% by May with deal
    no_steps = baseline * (1 + np.linspace(0, -0.20, 5))  # -20% by May without action
    
    plt.figure(figsize=(10, 6))
    plt.plot(time, steps_taken, label='Steps Taken (Mar-a-Lago Accord)', color='#4CAF50', lw=2)
    plt.plot(time, no_steps, label='No Steps Taken', color='#FF5733', lw=2)
    plt.title('S&P 500 Scenarios Post-Tariffs\n(April-May 2025 Prediction)', fontsize=14)
    plt.xlabel('Month (April=1)', fontsize=12)
    plt.ylabel('SPY Value ($)', fontsize=12)
    plt.legend(fontsize=10)
    plt.text(0.5, 0.95, 'Steps Could Stabilize; Inaction Risks Decline', 
             transform=plt.gca().transAxes, fontsize=10, ha='center', bbox=dict(facecolor='white', alpha=0.8))
    plt.tight_layout()
    plt.savefig('stock_scenarios.png')
    plt.show()

# Graphic 3: Sector Performance
def plot_sector_performance():
    sectors = ['Manufacturing', 'Retail', 'Tech', 'Energy', 'Exporters']
    performance = [0, -10, -7, -7, -14]
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(sectors, performance, color=['#4CAF50', '#FF5733', '#3498DB', '#FFC107', '#9C27B0'], 
                   edgecolor='black')
    plt.title('Sector Performance Under Tariff Scenario 3\n(Retaliation)', fontsize=14)
    plt.ylabel('Stock Price Change (%)', fontsize=12)
    plt.ylim(-10, 15)
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 0.5 if yval >= 0 else yval - 1, f'{yval}%', 
                 ha='center', va='bottom' if yval >= 0 else 'top', fontsize=10)
    plt.text(0.5, 0.95, 'Domestic Sectors Gain, Exporters Lag\nDue to Strong Dollar', 
             transform=plt.gca().transAxes, fontsize=10, ha='center', bbox=dict(facecolor='white', alpha=0.8))
    plt.tight_layout()
    plt.savefig('sector_performance.png')
    plt.show()

# Bonus Graphic: Disney and Nvidia Predictions
def plot_dis_nvda_predictions():
    time = np.arange(1, 6)  # April to August
    dis_steps = [92.51, 95, 98, 100, 102.50]  # DIS with steps
    dis_no_steps = [92.51, 90, 88, 86, 85]  # DIS without steps
    nvda_steps = [114, 118, 122, 125, 127.50]  # NVDA with steps
    nvda_no_steps = [114, 110, 106, 103, 100]  # NVDA without steps
    
    plt.figure(figsize=(10, 6))
    plt.plot(time, dis_steps, label='Disney (DIS) - Steps Taken', color='#FF5733', lw=2)
    plt.plot(time, dis_no_steps, label='Disney (DIS) - No Steps', color='#FF5733', lw=2, linestyle='--')
    plt.plot(time, nvda_steps, label='Nvidia (NVDA) - Steps Taken', color='#3498DB', lw=2)
    plt.plot(time, nvda_no_steps, label='Nvidia (NVDA) - No Steps', color='#3498DB', lw=2, linestyle='--')
    plt.title('Disney & Nvidia Under Tariff Scenarios\n(April-May 2025 Prediction)', fontsize=14)
    plt.xlabel('Month (April=1)', fontsize=12)
    plt.ylabel('Stock Price ($)', fontsize=12)
    plt.legend(fontsize=10)
    plt.text(0.5, 0.95, 'Steps vs. No Steps Impact', 
             transform=plt.gca().transAxes, fontsize=10, ha='center', bbox=dict(facecolor='white', alpha=0.8))
    plt.tight_layout()
    plt.savefig('dis_nvda_predictions.png')
    plt.show()

if __name__ == "__main__":
    plot_tariff_offset()
    plot_stock_scenarios()
    plot_sector_performance()
    plot_dis_nvda_predictions()
