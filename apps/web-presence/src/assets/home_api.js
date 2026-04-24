/**
 * home_api.js - API Fetching Utilities
 * Handles all API calls and data fetching for Winton's Corner homepage
 */

const API = {
    /**
     * Fetch Discord widget data for voice channels
     */
    async getDiscordChannels() {
        try {
            const response = await fetch('https://discord.com/api/guilds/1425571463192121354/widget.json?th' + Math.round(new Date().getTime()/180000));
            if (!response.ok) throw new Error('Failed to fetch Discord channels');
            return await response.json();
        } catch (error) {
            console.error('Discord API Error:', error);
            return null;
        }
    },

    /**
     * Fetch top workshop codes
     */
    async getWorkshopCodes(limit = 5) {
        try {
            const response = await fetch(`/api/workshop_codes?origin_context_id=eq.00000000-0000-0000-0001-000000000000&order=copy_count.desc&limit=5`);
            if (!response.ok) throw new Error('Failed to fetch workshop codes');
            return await response.json();
        } catch (error) {
            console.error('Workshop API Error:', error);
            return null;
        }
    },

    /**
     * Fetch LFG (Looking for Group) posts
     */
    async getLFGParties() {
        try {
            const response = await fetch('/api/parties?order=created_at.desc&limit=10');
            if (!response.ok) throw new Error('Failed to fetch LFG parties');
            return await response.json();
        } catch (error) {
            console.error('LFG API Error:', error);
            return null;
        }
    },

    /**
     * Fetch latest news/update post
     */
    async getLatestNews() {
        try {
            const response = await fetch('/api/updates?limit=1');
            if (!response.ok) throw new Error('Failed to fetch news');
            return await response.json();
        } catch (error) {
            console.error('News API Error:', error);
            return null;
        }
    }
};
