import express from 'express';
import { NseIndia } from 'stock-nse-india';

const app = express();
const nse = new NseIndia();

app.get('/quote/:symbol', async (req, res) => {
    try {
        const symbol = req.params.symbol.replace('.NS', '').replace('.BO', '');
        const data = await nse.getEquityDetails(symbol);
        res.json(data);
    } catch (error) {
        console.error(`Error fetching data for ${req.params.symbol}:`, error.message);
        res.status(500).json({ error: error.message });
    }
});

const PORT = 3000;
app.listen(PORT, () => {
    console.log(`NSE Market Service running on port ${PORT}`);
});
