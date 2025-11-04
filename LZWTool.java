import java.io.*;
import java.util.*;
 
public class LZWTool {

    /**
     * I have got this to basically do:
     * - Variable-width codewords (minW to maxW bits)
     * - Multiple eviction policies: freeze, reset, LRU, LFU
     * - O(1) LRU and LFU tracking using doubly-linked hashmaps
     * - Optimized for performance (StringBuilder pooling, cached operations, boolean arrays)
     * - Extended ASCII alphabet support (0-255)
     */
 
    //============================================
    // Command-line Arguments
    //============================================

    /** Compression or expansion mode */
    private static String mode;
 
    /** Minimum codeword width in bits (must be large enough to encode alphabet + EOF) */
    private static int minW = 9;
 
    /** Maximum codeword width in bits (limits codebook size to 2^maxW entries) */
    private static int maxW = 16;
 
    /** Eviction policy when codebook is full: freeze, reset, lru, lfu */
    private static String policy = "freeze";
 
    /** Path to the alphabet file for initializing the codebook */
    private static String alphabetPath;
 
    /** This is not part of the main algorith, this is for debug only */
    /** Debug flag - set to true to enable detailed compression/decompression logs */
    private static final boolean DEBUG = false;
 
    
    //============================================
    // LRU Tracker for Compression (String keys)
    //============================================
    /**
     * O(1) LRU tracker using doubly-linked list + HashMap
     *
     * Design: Sentinel nodes (head/tail) eliminate null checks
     * - head.next points to most recently used (MRU)
     * - tail.prev points to least recently used (LRU)
     * - HashMap provides O(1) lookup of nodes by key
     *
     * This allows O(1) operations for:
     * - use(key): Mark key as recently used
     * - findLRU(): Find least recently used key
     * - remove(key): Remove a key from tracking
     */
    private static class LRUTracker {
        /** Node in doubly-linked list */
        private class Node {
            String key;
            Node prev, next;
            Node(String key) { this.key = key; }
        }
 
        private final HashMap<String, Node> map;  // Key -> Node mapping for O(1) lookup
        private final Node head, tail;  // Sentinels: head.next = MRU, tail.prev = LRU
 
        /**
         * Initialize LRU tracker with given capacity
         * @param capacity Maximum number of entries to track
         */
        LRUTracker(int capacity) {
            this.map = new HashMap<>(capacity);
            this.head = new Node(null);
            this.tail = new Node(null);
            head.next = tail;
            tail.prev = head;
            debug("LRUTracker initialized with capacity: " + capacity);
        }
 
        /**
         * Mark a key as recently used (move to front of list)
         * If key doesn't exist, add it to front
         * @param key The key to mark as used
         */
        void use(String key) {
            Node node = map.get(key);
            if (node != null) {
                // Already exists - move to front (most recently used position)
                removeNode(node);
                addToFront(node);
            } else {
                // New entry - add to front
                node = new Node(key);
                map.put(key, node);
                addToFront(node);
            }
            debug("LRUTracker.use('" + escapeString(key) + "'), mapSize=" + map.size());
        }
 
        /**
         * Find the least recently used key
         * @return The LRU key, or null if empty
         */
        String findLRU() {
            if (tail.prev == head) return null; // Empty list
            String lruKey = tail.prev.key;
            debug("LRUTracker.findLRU() -> '" + escapeString(lruKey) + "'");
            return lruKey;
        }
 
        /**
         * Remove a key from tracking
         * @param key The key to remove
         */
        void remove(String key) {
            Node node = map.remove(key);
            if (node != null) {
                removeNode(node);
            }
            debug("LRUTracker.remove('" + escapeString(key) + "'), mapSize=" + map.size());
        }
 
        /**
         * Check if a key is being tracked
         * @param key The key to check
         * @return true if key is tracked, false otherwise
         */
        boolean contains(String key) {
            return map.containsKey(key);
        }
 
        /**
         * Add node to front of list (most recently used position)
         * @param node The node to add to front
         */
        private void addToFront(Node node) {
            node.next = head.next;
            node.prev = head;
            head.next.prev = node;
            head.next = node;
        }
 
        /**
         * Remove node from list (maintains prev/next links)
         * @param node The node to remove
         */
        private void removeNode(Node node) {
            node.prev.next = node.next;
            node.next.prev = node.prev;
        }
 
        /**
         * Debug: Print current state of LRU tracker
         */
        void printState() {
            debug("LRUTracker state (size=" + map.size() + "):");
            Node current = head.next;
            while (current != tail) {
                debug("  '" + escapeString(current.key) + "'");
                current = current.next;
            }
        }
    }
 
    //============================================
    // LRU Tracker for Decompression (Integer keys for codes)
    //============================================
    /**
     * O(1) LRU tracker for decoder - uses Integer keys (codewords) instead of Strings
     * Same design as LRUTracker but for integer codes during decompression
     * 
     * Design: Sentinel nodes (head/tail) eliminate null checks
     * - head.next points to most recently used (MRU)
     * - tail.prev points to least recently used (LRU)
     * - HashMap provides O(1) lookup of nodes by code
     */
    private static class LRUTrackerDecoder {
        /** Node in doubly-linked list */
        private class Node {
            int code;
            Node prev, next;
            Node(int code) { this.code = code; }
        }
 
        private final HashMap<Integer, Node> map;  // Code -> Node mapping for O(1) lookup
        private final Node head, tail;  // Sentinels: head.next = MRU, tail.prev = LRU
 
        /**
         * Initialize LRU tracker for decoder with given capacity
         * @param capacity Maximum number of entries to track
         */
        LRUTrackerDecoder(int capacity) {
            this.map = new HashMap<>(capacity);
            this.head = new Node(-1);
            this.tail = new Node(-1);
            head.next = tail;
            tail.prev = head;
            debug("LRUTrackerDecoder initialized with capacity: " + capacity);
        }
 
        /**
         * Mark a code as recently used (move to front of list)
         * If code doesn't exist, add it to front
         * @param code The code to mark as used
         */
        void use(int code) {
            Node node = map.get(code);
            if (node != null) {
                removeNode(node);
                addToFront(node);
            } else {
                node = new Node(code);
                map.put(code, node);
                addToFront(node);
            }
            debug("LRUTrackerDecoder.use(code=" + code + "), mapSize=" + map.size());
        }
 
        /**
         * Find the least recently used code
         * @return The LRU code, or -1 if empty
         */
        int findLRU() {
            if (tail.prev == head) return -1;
            int lruCode = tail.prev.code;
            debug("LRUTrackerDecoder.findLRU() -> code=" + lruCode);
            return lruCode;
        }
 
        /**
         * Remove a code from tracking
         * @param code The code to remove
         */
        void remove(int code) {
            Node node = map.remove(code);
            if (node != null) {
                removeNode(node);
            }
            debug("LRUTrackerDecoder.remove(code=" + code + "), mapSize=" + map.size());
        }
 
        /**
         * Add node to front of list (most recently used position)
         * @param node The node to add to front
         */
        private void addToFront(Node node) {
            node.next = head.next;
            node.prev = head;
            head.next.prev = node;
            head.next = node;
        }
 
        /**
         * Remove node from list (maintains prev/next links)
         * @param node The node to remove
         */
        private void removeNode(Node node) {
            node.prev.next = node.next;
            node.next.prev = node.prev;
        }
 
        /**
         * Debug: Print current state of LRU tracker for decoder
         */
        void printState() {
            debug("LRUTrackerDecoder state (size=" + map.size() + "):");
            Node current = head.next;
            while (current != tail) {
                debug("  code=" + current.code);
                current = current.next;
            }
        }
    }
 
    //============================================
    // LFU Tracker for Compression (String keys)
    //============================================
    /**
     * O(1) LFU tracker using frequency buckets + doubly-linked lists
     *
     * Design:
     * - Each frequency has its own doubly-linked list of keys
     * - keyToNode: Maps key -> Node (for O(1) lookup)
     * - freqToList: Maps frequency -> FreqList (for O(1) bucket access)
     * - minFreq: Tracks minimum frequency for fast LFU lookup
     *
     * When a key is used:
     * 1. Remove from current frequency list
     * 2. Increment frequency
     * 3. Add to new frequency list
     * 4. Update minFreq if needed
     */
    private static class LFUTracker {
        /** Node in doubly-linked list with frequency tracking */
        private class Node {
            String key;
            int freq;
            Node prev, next;
            Node(String key, int freq) { this.key = key; this.freq = freq; }
        }
 
        /** Doubly-linked list for a specific frequency */
        private class FreqList {
            Node head, tail;
            
            /**
             * Initialize frequency list with sentinel nodes
             */
            FreqList() {
                head = new Node(null, 0);
                tail = new Node(null, 0);
                head.next = tail;
                tail.prev = head;
            }
            
            /**
             * Add node to front of frequency list
             * @param node The node to add
             */
            void addToFront(Node node) {
                node.next = head.next;
                node.prev = head;
                head.next.prev = node;
                head.next = node;
            }
            
            /**
             * Remove node from frequency list
             * @param node The node to remove
             */
            void remove(Node node) {
                node.prev.next = node.next;
                node.next.prev = node.prev;
            }
            
            /**
             * Check if frequency list is empty
             * @return true if empty, false otherwise
             */
            boolean isEmpty() {
                return head.next == tail;
            }
            
            /**
             * Get first node in frequency list
             * @return First node, or null if empty
             */
            Node getFirst() {
                return head.next == tail ? null : head.next;
            }
        }
 
        private final HashMap<String, Node> keyToNode;       // Key -> Node mapping
        private final HashMap<Integer, FreqList> freqToList; // Frequency -> List mapping
        private int minFreq;                                  // Current minimum frequency
 
        /**
         * Initialize LFU tracker with given capacity
         * @param capacity Maximum number of entries to track
         */
        LFUTracker(int capacity) {
            this.keyToNode = new HashMap<>(capacity);
            this.freqToList = new HashMap<>();
            this.minFreq = 0;
            debug("LFUTracker initialized with capacity: " + capacity);
        }
 
        /**
         * Mark a key as used (increment its frequency)
         * @param key The key to mark as used
         */
        void use(String key) {
            Node node = keyToNode.get(key);
            if (node == null) {
                // New key: add with frequency 1
                node = new Node(key, 1);
                keyToNode.put(key, node);
                freqToList.computeIfAbsent(1, k -> new FreqList()).addToFront(node);
                minFreq = 1;
                debug("LFUTracker.use('" + escapeString(key) + "') NEW freq=1, mapSize=" + keyToNode.size());
            } else {
                // Existing key: increment frequency
                int oldFreq = node.freq;
                FreqList oldList = freqToList.get(oldFreq);
                oldList.remove(node);
 
                // If we just emptied the minimum frequency bucket, increment minFreq
                if (oldFreq == minFreq && oldList.isEmpty()) {
                    minFreq = oldFreq + 1;
                }
 
                node.freq++;
                freqToList.computeIfAbsent(node.freq, k -> new FreqList()).addToFront(node);
                debug("LFUTracker.use('" + escapeString(key) + "') freq=" + node.freq + ", mapSize=" + keyToNode.size());
            }
        }
 
        /**
         * Find the least frequently used key
         * @return The LFU key, or null if empty
         */
        String findLFU() {
            FreqList minList = freqToList.get(minFreq);
            if (minList == null || minList.isEmpty()) return null;
            Node lfuNode = minList.getFirst();
            debug("LFUTracker.findLFU() -> '" + escapeString(lfuNode.key) + "' with freq=" + lfuNode.freq);
            return lfuNode.key;
        }
 
        /**
         * Remove a key from tracking
         * @param key The key to remove
         */
        void remove(String key) {
            Node node = keyToNode.remove(key);
            if (node != null) {
                FreqList list = freqToList.get(node.freq);
                list.remove(node);
                debug("LFUTracker.remove('" + escapeString(key) + "'), mapSize=" + keyToNode.size());
            }
        }
 
        /**
         * Check if a key is being tracked
         * @param key The key to check
         * @return true if key is tracked, false otherwise
         */
        boolean contains(String key) {
            return keyToNode.containsKey(key);
        }
 
        /**
         * Debug: Print current state of LFU tracker
         */
        void printState() {
            debug("LFUTracker state (size=" + keyToNode.size() + ", minFreq=" + minFreq + "):");
            for (Map.Entry<Integer, FreqList> entry : freqToList.entrySet()) {
                int freq = entry.getKey();
                FreqList list = entry.getValue();
                Node current = list.head.next;
                while (current != list.tail) {
                    debug("  '" + escapeString(current.key) + "' -> freq=" + freq);
                    current = current.next;
                }
            }
        }
    }
 
    //============================================
    // LFU Tracker for Decompression (Integer keys)
    //============================================
    /**
     * O(1) LFU tracker for decoder - uses Integer keys (codewords) instead of Strings
     * Same design as LFUTracker but for integer codes during decompression
     * 
     * Design:
     * - Each frequency has its own doubly-linked list of codes
     * - codeToNode: Maps code -> Node (for O(1) lookup)
     * - freqToList: Maps frequency -> FreqList (for O(1) bucket access)
     * - minFreq: Tracks minimum frequency for fast LFU lookup
     */
    private static class LFUTrackerDecoder {
        /** Node in doubly-linked list with frequency tracking */
        private class Node {
            int code;
            int freq;
            Node prev, next;
            Node(int code, int freq) { this.code = code; this.freq = freq; }
        }
 
        /** Doubly-linked list for a specific frequency */
        private class FreqList {
            Node head, tail;
            
            /**
             * Initialize frequency list with sentinel nodes
             */
            FreqList() {
                head = new Node(-1, 0);
                tail = new Node(-1, 0);
                head.next = tail;
                tail.prev = head;
            }
            
            /**
             * Add node to front of frequency list
             * @param node The node to add
             */
            void addToFront(Node node) {
                node.next = head.next;
                node.prev = head;
                head.next.prev = node;
                head.next = node;
            }
            
            /**
             * Remove node from frequency list
             * @param node The node to remove
             */
            void remove(Node node) {
                node.prev.next = node.next;
                node.next.prev = node.prev;
            }
            
            /**
             * Check if frequency list is empty
             * @return true if empty, false otherwise
             */
            boolean isEmpty() {
                return head.next == tail;
            }
            
            /**
             * Get first node in frequency list
             * @return First node, or null if empty
             */
            Node getFirst() {
                return head.next == tail ? null : head.next;
            }
        }
 
        private final HashMap<Integer, Node> codeToNode;      // Code -> Node mapping
        private final HashMap<Integer, FreqList> freqToList;  // Frequency -> List mapping
        private int minFreq;                                   // Current minimum frequency
 
        /**
         * Initialize LFU tracker for decoder with given capacity
         * @param capacity Maximum number of entries to track
         */
        LFUTrackerDecoder(int capacity) {
            this.codeToNode = new HashMap<>(capacity);
            this.freqToList = new HashMap<>();
            this.minFreq = 0;
            debug("LFUTrackerDecoder initialized with capacity: " + capacity);
        }
 
        /**
         * Mark a code as used (increment its frequency)
         * @param code The code to mark as used
         */
        void use(int code) {
            Node node = codeToNode.get(code);
            if (node == null) {
                node = new Node(code, 1);
                codeToNode.put(code, node);
                freqToList.computeIfAbsent(1, k -> new FreqList()).addToFront(node);
                minFreq = 1;
                debug("LFUTrackerDecoder.use(code=" + code + ") NEW freq=1, mapSize=" + codeToNode.size());
            } else {
                int oldFreq = node.freq;
                FreqList oldList = freqToList.get(oldFreq);
                oldList.remove(node);
 
                if (oldFreq == minFreq && oldList.isEmpty()) {
                    minFreq = oldFreq + 1;
                }
 
                node.freq++;
                freqToList.computeIfAbsent(node.freq, k -> new FreqList()).addToFront(node);
                debug("LFUTrackerDecoder.use(code=" + code + ") freq=" + node.freq + ", mapSize=" + codeToNode.size());
            }
        }
 
        /**
         * Find the least frequently used code
         * @return The LFU code, or -1 if empty
         */
        int findLFU() {
            FreqList minList = freqToList.get(minFreq);
            if (minList == null || minList.isEmpty()) return -1;
            Node lfuNode = minList.getFirst();
            debug("LFUTrackerDecoder.findLFU() -> code=" + lfuNode.code + " with freq=" + lfuNode.freq);
            return lfuNode.code;
        }
 
        /**
         * Remove a code from tracking
         * @param code The code to remove
         */
        void remove(int code) {
            Node node = codeToNode.remove(code);
            if (node != null) {
                FreqList list = freqToList.get(node.freq);
                list.remove(node);
                debug("LFUTrackerDecoder.remove(code=" + code + "), mapSize=" + codeToNode.size());
            }
        }
 
        /**
         * Debug: Print current state of LFU tracker for decoder
         */
        void printState() {
            debug("LFUTrackerDecoder state (size=" + codeToNode.size() + ", minFreq=" + minFreq + "):");
            for (Map.Entry<Integer, FreqList> entry : freqToList.entrySet()) {
                int freq = entry.getKey();
                FreqList list = entry.getValue();
                Node current = list.head.next;
                while (current != list.tail) {
                    debug("  code=" + current.code + " -> freq=" + freq);
                    current = current.next;
                }
            }
        }
    }

    //============================================
    // Helper Methods
    //============================================
 
    /** Print debug message if DEBUG is enabled */
    private static void debug(String msg) {
        if (DEBUG) System.err.println("[DEBUG] " + msg);
    }
 
    /** Escape special characters for debug output */
    private static String escapeString(String s) {
        if (s == null) return "null";
        return s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t");
    }
 
    //============================================
    // Argument Validation
    //============================================
 
    /**
     * Validate compression-specific arguments
     * Checks:
     * - Alphabet file is specified
     * - minW >= 1 (cannot write 0-bit codewords)
     * - maxW >= minW
     * - maxW not absurdly large (warns if > 32)
     */
    private static void validateCompressionArgs() {
        if (alphabetPath == null) {
            System.err.println("Missing required argument: --alphabet is required for compression mode");
            System.exit(1);
        }
        if (minW < 1) {
            System.err.println("Invalid argument: --minW must be at least 1 (cannot write 0-bit codewords)");
            System.exit(1);
        }
        if (maxW < minW) {
            System.err.println("Invalid argument: --maxW (" + maxW + ") must be >= --minW (" + minW + ")");
            System.exit(1);
        }
        if (maxW > 32) {
            System.err.println("Warning: --maxW (" + maxW + ") is very large, may cause issues");
        }
    }
 
    /**
     * Parse command-line arguments
     * Validates argument format and catches NumberFormatException for numeric args
     * @param args Command-line arguments
     */
    private static void parseArguments(String[] args) {
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--mode":
                    if (i + 1 >= args.length) {
                        System.err.println("Missing value for argument: --mode requires a value (compress or expand)");
                        System.exit(1);
                    }
                    mode = args[++i];
                    break;
                case "--minW":
                    if (i + 1 >= args.length) {
                        System.err.println("Missing value for argument: --minW requires a numeric value");
                        System.exit(1);
                    }
                    try {
                        minW = Integer.parseInt(args[++i]);
                    } catch (NumberFormatException e) {
                        System.err.println("Invalid value for --minW: '" + args[i] + "' is not a valid integer");
                        System.exit(1);
                    }
                    break;
                case "--maxW":
                    if (i + 1 >= args.length) {
                        System.err.println("Missing value for argument: --maxW requires a numeric value");
                        System.exit(1);
                    }
                    try {
                        maxW = Integer.parseInt(args[++i]);
                    } catch (NumberFormatException e) {
                        System.err.println("Invalid value for --maxW: '" + args[i] + "' is not a valid integer");
                        System.exit(1);
                    }
                    break;
                case "--policy":
                    if (i + 1 >= args.length) {
                        System.err.println("Missing value for argument: --policy requires a value (freeze, reset, lru, or lfu)");
                        System.exit(1);
                    }
                    policy = args[++i];
                    break;
                case "--alphabet":
                    if (i + 1 >= args.length) {
                        System.err.println("Missing value for argument: --alphabet requires a file path");
                        System.exit(1);
                    }
                    alphabetPath = args[++i];
                    break;
                default:
                    System.err.println("Unknown argument: '" + args[i] + "' is not a recognized option");
                    System.exit(2);
            }
        }
    }
 
    /**
     * Main entry point
     * @param args Command-line arguments
     */
    public static void main(String[] args) {
 
        if (args.length == 0) {
            System.err.println("No arguments provided. Usage:");
            System.err.println("  Compress: java LZWTool --mode compress --alphabet <file> [--minW <n>] [--maxW <n>] [--policy <name>]");
            System.err.println("  Expand:   java LZWTool --mode expand");
            System.exit(1);
        }
 
        parseArguments(args);
 
        if (mode == null) {
            System.err.println("Missing required argument: --mode must be specified (compress or expand)");
            System.exit(1);
        }
 
        if (mode.equals("compress")) {
            validateCompressionArgs();
 
            List<Character> alphabet = loadAlphabet(alphabetPath);
 
            if (alphabet == null) {
                System.err.println("Failed to load alphabet: Could not read file '" + alphabetPath + "' (file may not exist or is not readable)");
                System.exit(1);
            }
 
            if (alphabet.size() == 0) {
                System.err.println("Invalid alphabet: Alphabet file '" + alphabetPath + "' contains no valid characters");
                System.exit(1);
            }
 
            compress(minW, maxW, policy, alphabet);
 
        } else if (mode.equals("expand")) {
            expand();
        } else {
            System.err.println("Invalid value for --mode: '" + mode + "' is not valid (must be 'compress' or 'expand')");
            System.exit(1);
        }
    }
 
    /**
     * Load alphabet from file
     *
     * Uses boolean array instead of HashSet for duplicate tracking
     * - boolean[256] provides O(1) lookup without boxing overhead
     * - HashSet would require boxing char -> Character on every lookup
     * - For Extended ASCII (0-255), boolean array is both faster and simpler
     *
     * One character per line (only first character of each line is used)
     * Always includes CR (\r) and LF (\n) for text file compatibility
     *
     * @param path Path to alphabet file
     * @return List of unique characters, or null if file cannot be read
     */
    private static List<Character> loadAlphabet(String path) {
 
        // Pre-allocate with max Extended ASCII size to avoid ArrayList resizing
        List<Character> alphabet = new ArrayList<>(256);
 
        // Use boolean array instead of HashSet
        // - No boxing overhead (char stays primitive until added to alphabet)
        // - O(1) lookup via direct array indexing
        // - Works for Extended ASCII range (0-255)
        boolean[] seen = new boolean[256];
 
        // Always include CR and LF in the alphabet (required for text files)
        alphabet.add('\r'); seen['\r'] = true;
        alphabet.add('\n'); seen['\n'] = true;
 
        // Read alphabet file as UTF-8 (standard text encoding)
        try (InputStreamReader reader = new InputStreamReader(new FileInputStream(path), "UTF-8")) {
 
            // Pre-allocate StringBuilder with typical line length
            StringBuilder lineBuffer = new StringBuilder(16);
            int c; // Current character (int to detect EOF = -1)
 
            // Read character-by-character to handle different line ending formats
            // (Unix: \n, Windows: \r\n, Old Mac: \r)
            while ((c = reader.read()) != -1) {
                if (c == '\n') {
                    // Line ending found - process the line
 
                    if (lineBuffer.length() > 0) {
                        // Use primitive char to avoid boxing
                        // (auto-boxing to Character happens only on alphabet.add())
                        char symbol = lineBuffer.charAt(0);
 
                        // boolean array lookup instead of HashSet.contains()
                        if (!seen[symbol]) {
                            seen[symbol] = true;
                            alphabet.add(symbol);
                        }
                    }
                    // Note: Empty lines are ignored
 
                    // setLength(0) resets buffer without deallocation
                    lineBuffer.setLength(0);
                } else {
                    // Regular character - accumulate in line buffer
                    lineBuffer.append((char) c);
                }
            }
 
            // Handle last line if file doesn't end with newline
            if (lineBuffer.length() > 0) {
                char symbol = lineBuffer.charAt(0);
                if (!seen[symbol]) {
                    seen[symbol] = true;
                    alphabet.add(symbol);
                }
            }
        } catch (IOException e) {
            return null; // Signal error to caller
        }
 
        return alphabet;
    }
 
    //============================================
    // Main Algorithm
    //============================================

    /**
     * Compress input using LZW algorithm with variable-width encoding
     *
     * I should note the following:
     * 1. StringBuilder pooling - Reuse nextBuilder instead of creating new StringBuilder each iteration
     * 2. String caching - Single toString() call when both LRU/LFU need the string
     * 3. Boolean array validation - O(1) alphabet validation without HashSet overhead
     * 4. Cached bit-shift - Cache (1 << W) threshold instead of recalculating every iteration
     *
     * Algorithm:
     * 1. Initialize dictionary with alphabet
     * 2. Read input character by character
     * 3. Find longest match in dictionary
     * 4. Output code for match
     * 5. Add match + next character to dictionary (if not full)
     * 6. Handle eviction based on policy when dictionary is full
     *
     * @param minW Minimum codeword width in bits
     * @param maxW Maximum codeword width in bits
     * @param policy Eviction policy (freeze, reset, lru, lfu)
     * @param alphabet List of valid input characters
     */
    private static void compress(int minW, int maxW, String policy, List<Character> alphabet) {
        debug("\n=== STARTING COMPRESSION ===");
        debug("Policy: " + policy + ", minW=" + minW + ", maxW=" + maxW);
 
        writeHeader(minW, maxW, policy, alphabet);
 
        // Dictionary maps String patterns -> Integer codes
        TSTmod<Integer> dictionary = new TSTmod<>();
 
        int W = minW;                    // Current codeword width
        int maxCode = 1 << maxW;         // Maximum number of codes
        int alphabetSize = alphabet.size();
 
        // Use boolean array for alphabet validation
        // - HashSet would require boxing char -> Character on every contains() call
        // - boolean[256] provides O(1) validation via direct array indexing
        // - Works for Extended ASCII (0-255), which is our design constraint
        boolean[] validChar = new boolean[256];
        for (Character symbol : alphabet) {
            validChar[symbol] = true;
        }
 
        // Initialize dictionary with alphabet
        int nextCode = 0;
        StringBuilder sb = new StringBuilder(1);
 
        debug("\nInitializing codebook with alphabet:");
        for (Character symbol : alphabet) {
            sb.setLength(0);
            sb.append(symbol);
            dictionary.put(sb, nextCode);
            debug("  '" + escapeString(String.valueOf(symbol)) + "' -> code " + nextCode);
            nextCode++;
        }
 
        int EOF_CODE = nextCode++;
        debug("EOF_CODE = " + EOF_CODE);
 
        // Policy flags
        boolean resetPolicy = policy.equals("reset");
        boolean lruPolicy = policy.equals("lru");
        boolean lfuPolicy = policy.equals("lfu");
 
        int RESET_CODE = -1;
        if (resetPolicy) {
            RESET_CODE = nextCode++;
            debug("RESET_CODE = " + RESET_CODE);
        }
 
        int initialNextCode = nextCode;
        debug("initialNextCode = " + initialNextCode);
 
        // Initialize LRU tracker if needed
        LRUTracker lruTracker = null;
        if (lruPolicy) {
            lruTracker = new LRUTracker(maxCode);
        }
 
        // Initialize LFU tracker if needed
        LFUTracker lfuTracker = null;
        if (lfuPolicy) {
            lfuTracker = new LFUTracker(maxCode);
        }
 
        // Pre-allocate alphabet keys for reset mode (avoids StringBuilder creation on each reset)
        StringBuilder[] alphabetKeys = null;
        if (resetPolicy) {
            alphabetKeys = new StringBuilder[alphabetSize];
            for (int i = 0; i < alphabetSize; i++)
                alphabetKeys[i] = new StringBuilder(String.valueOf(alphabet.get(i)));
        }
 
        debug("maxCode = " + maxCode);
 
        // Handle empty input
        if (BinaryStdIn.isEmpty()) {
            debug("Input is empty, closing.");
            BinaryStdOut.close();
            return;
        }
 
        // Read first character and validate
        char c = BinaryStdIn.readChar();
        if (!validChar[c]) {
            System.err.println("Input contains byte value " + (int) c + " which is not in the alphabet");
            System.exit(1);
        }
        StringBuilder current = new StringBuilder().append(c);
        debug("\nFirst character: '" + escapeString(String.valueOf(c)) + "'");
 
        int step = 0;
        debug("\n=== ENCODING LOOP ===");
 
        // StringBuilder pooling
        // Reuse this StringBuilder instead of creating new ones every iteration
        // Saves i believe around 1 million allocations per MB of input
        StringBuilder nextBuilder = new StringBuilder(256);
 
        // Cache bit-shift threshold
        // Recalculating (1 << W) every iteration wastes CPU cycles
        // W only changes ~10 times but loop runs millions of times
        // Again caching reduces ~1M shift operations to ~10 for 1MB file
        int widthThreshold = 1 << W;
 
        // Main compression loop
        while (!BinaryStdIn.isEmpty()) {
 
            c = BinaryStdIn.readChar();
 
            // Validate character is in alphabet
            if (!validChar[c]) {
                System.err.println("Input contains byte value " + (int) c + " which is not in the alphabet");
                System.exit(1);
            }
 
            // Reuse nextBuilder instead of creating new StringBuilder
            nextBuilder.setLength(0);
            nextBuilder.append(current).append(c);
 
            step++;
            debug("\n--- Step " + step + " ---");
            debug("Read char: '" + escapeString(String.valueOf(c)) + "'");
            debug("current = '" + escapeString(current.toString()) + "', next = '" + escapeString(nextBuilder.toString()) + "'");
 
            if (dictionary.contains(nextBuilder)) {
                // Pattern exists - extend current match
                debug("Codebook CONTAINS '" + escapeString(nextBuilder.toString()) + "' - extending current");
                current.setLength(0);
                current.append(nextBuilder);
            } else {
                // Pattern not in dictionary - output current and add new pattern
 
                int outputCode = dictionary.get(current);
                debug("Codebook does NOT contain '" + escapeString(nextBuilder.toString()) + "'");
                debug("OUTPUT: code=" + outputCode + " for '" + escapeString(current.toString()) + "' (W=" + W + " bits)");
                BinaryStdOut.write(outputCode, W);
 
                // String caching
                // If both LRU and LFU are active, only call toString() once
                // Saves around half??? of String allocations when multiple policies are used
                String currentStr = null;
                if (lruPolicy || lfuPolicy) {
                    currentStr = current.toString();
                }
 
                // Update LRU tracker (only if entry already exists)
                if (lruPolicy && lruTracker.contains(currentStr)) {
                    lruTracker.use(currentStr);
                }
 
                // Update LFU tracker (only if entry already exists)
                if (lfuPolicy && lfuTracker.contains(currentStr)) {
                    lfuTracker.use(currentStr);
                }
 
                // Add new pattern to dictionary if not full
                if (nextCode < maxCode) {
                    // Use cached threshold instead of recalculating (1 << W)
                    // Increase bit width when we cross the threshold
                    if (nextCode >= widthThreshold && W < maxW) {
                        W++;
                        widthThreshold = 1 << W;  // Update cache only when W changes
                        debug("Increased W to " + W);
                    }
 
                    // LRU eviction: Remove least recently used entry if at capacity
                    if (lruPolicy && nextCode == maxCode - 1) {
                        debug("LRU: At capacity, need to evict");
                        lruTracker.printState();
                        String lruEntry = lruTracker.findLRU();
                        if (lruEntry != null) {
                            debug("EVICTING: '" + escapeString(lruEntry) + "'");
                            nextBuilder.setLength(0);
                            nextBuilder.append(lruEntry);
                            dictionary.put(nextBuilder, null);  // Remove from dictionary
                            lruTracker.remove(lruEntry);
                        }
                    }
 
                    // LFU eviction: Remove least frequently used entry if at capacity
                    if (lfuPolicy && nextCode == maxCode - 1) {
                        debug("LFU: At capacity, need to evict");
                        lfuTracker.printState();
                        String lfuEntry = lfuTracker.findLFU();
                        if (lfuEntry != null) {
                            debug("EVICTING: '" + escapeString(lfuEntry) + "'");
                            nextBuilder.setLength(0);
                            nextBuilder.append(lfuEntry);
                            dictionary.put(nextBuilder, null);  // Remove from dictionary
                            lfuTracker.remove(lfuEntry);
                        }
                    }
 
                    // Add new pattern to dictionary
                    nextBuilder.setLength(0);
                    nextBuilder.append(current).append(c);
                    String nextStr = nextBuilder.toString();
 
                    debug("ADDING to codebook: '" + escapeString(nextStr) + "' -> code " + nextCode);
                    dictionary.put(new StringBuilder(nextStr), nextCode);
 
                    // Track new entry in LRU
                    if (lruPolicy) {
                        lruTracker.use(nextStr);
                    }
 
                    // Track new entry in LFU
                    if (lfuPolicy) {
                        lfuTracker.use(nextStr);
                    }
 
                    nextCode++;
 
                } else {
                    // Dictionary full - handle based on policy
 
                    if (resetPolicy) {
                        // Reset policy, so we clear dictionary and start over
                        debug("RESET policy: codebook full");
 
                        // Check if we need to increase W before writing reset code
                        if (nextCode >= widthThreshold && W < maxW) {
                            W++;
                            widthThreshold = 1 << W;
                            debug("Increased W to " + W);
                        }
 
                        debug("OUTPUT RESET_CODE: " + RESET_CODE + " (W=" + W + " bits)");
                        BinaryStdOut.write(RESET_CODE, W);
 
                        // Reset dictionary to initial alphabet
                        debug("Resetting codebook to initial state");
                        dictionary = new TSTmod<>();
                        for (int i = 0; i < alphabetSize; i++)
                            dictionary.put(alphabetKeys[i], i);
 
                        nextCode = initialNextCode;
                        W = minW;
                        widthThreshold = 1 << W;  // Reset cached threshold
                        debug("Reset complete: nextCode=" + nextCode + ", W=" + W);
                    } else {
                        // Freeze: Do nothing, dictionary stays full
                        debug("FREEZE policy: codebook full, no action");
                    } // Note that we do not account for the LRU and LFU policies, because they are handled elsewhere
                }
 
                // Reset current to the new single character
                current.setLength(0);
                current.append(c);
                debug("current reset to: '" + escapeString(current.toString()) + "'");
            }
        }
 
        // Output final pattern
        debug("\n=== FINAL OUTPUT ===");
        if (current.length() > 0) {
            int outputCode = dictionary.get(current);
            debug("OUTPUT final: code=" + outputCode + " for '" + escapeString(current.toString()) + "' (W=" + W + " bits)");
            BinaryStdOut.write(outputCode, W);
 
            // Update trackers for final pattern
            String currentStr = null;
            if (lruPolicy || lfuPolicy) {
                currentStr = current.toString();
            }
 
            if (lruPolicy && lruTracker.contains(currentStr)) {
                lruTracker.use(currentStr);
            }
 
            if (lfuPolicy && lfuTracker.contains(currentStr)) {
                lfuTracker.use(currentStr);
            }
        }
 
        // Check if we need to increase W for EOF code
        if (nextCode >= widthThreshold && W < maxW) {
            W++;
            widthThreshold = 1 << W;
            debug("Increased W to " + W + " for EOF_CODE");
        }
 
        // Output EOF code
        debug("OUTPUT EOF_CODE: " + EOF_CODE + " (W=" + W + " bits)");
        BinaryStdOut.write(EOF_CODE, W);
 
        if (lruPolicy) {
            debug("\nFinal LRU state:");
            lruTracker.printState();
        }
 
        if (lfuPolicy) {
            debug("\nFinal LFU state:");
            lfuTracker.printState();
        }
 
        debug("\n=== COMPRESSION COMPLETE ===\n");
        BinaryStdOut.close();
    }
 
    /**
     * Decompress LZW-compressed input
     *
     * Cached bit-shift (same as compress)
     *
     * Algorithm:
     * 1. Read header to get parameters
     * 2. Initialize decoding table with alphabet
     * 3. Read codewords and decode
     * 4. Handle special case where codeword == nextCode (pattern = previous + previous[0])
     * 5. Add new patterns to dictionary
     * 6. Handle eviction based on policy
     *
     * @return void (writes decompressed data to BinaryStdOut)
     */
    private static void expand() {
        debug("\n=== STARTING DECOMPRESSION ===");
 
        Header h = readHeader();
 
        int maxCode = 1 << h.maxW;
        int W = h.minW;
        int alphabetSize = h.alphabetSize;
 
        int EOF_CODE = h.alphabetSize;
        int RESET_CODE = -1;
        boolean resetPolicy = (h.policy == 1);
        boolean lruPolicy = (h.policy == 2);
        boolean lfuPolicy = (h.policy == 3);
 
        int initialNextCode;
        if (resetPolicy) {
            RESET_CODE = h.alphabetSize + 1;
            initialNextCode = h.alphabetSize + 2;
        } else {
            initialNextCode = h.alphabetSize + 1;
        }
 
        int nextCode = initialNextCode;
 
        debug("maxCode = " + maxCode);
        debug("EOF_CODE = " + EOF_CODE);
        if (resetPolicy) debug("RESET_CODE = " + RESET_CODE);
        debug("initialNextCode = " + initialNextCode);
 
        // Initialize LRU/LFU trackers if needed
        LRUTrackerDecoder lruTracker = null;
        if (lruPolicy) {
            lruTracker = new LRUTrackerDecoder(maxCode);
        }
 
        LFUTrackerDecoder lfuTracker = null;
        if (lfuPolicy) {
            lfuTracker = new LFUTrackerDecoder(maxCode);
        }
 
        // Initialize decoding table with alphabet
        String[] dictionary = new String[maxCode];
        debug("\nInitializing decoding table:");
        for (int i = 0; i < h.alphabetSize; i++) {
            dictionary[i] = h.alphabet.get(i).toString();
            debug("  code " + i + " -> '" + escapeString(dictionary[i]) + "'");
        }
 
        if (BinaryStdIn.isEmpty()) {
            debug("Input is empty, closing.");
            BinaryStdOut.close();
            return;
        }
 
        // Read and output first codeword
        int prevCode = BinaryStdIn.readInt(W);
        debug("\nFirst codeword: " + prevCode + " (W=" + W + " bits)");
 
        if (prevCode == EOF_CODE) {
            debug("First code is EOF_CODE, closing.");
            BinaryStdOut.close();
            return;
        }
 
        if (prevCode < h.alphabetSize) {
            String val = dictionary[prevCode];
            debug("Decoded: '" + escapeString(val) + "'");
            debug("OUTPUT: '" + escapeString(val) + "'");
            BinaryStdOut.write(val);
        } else {
            System.err.println("Bad compressed code: " + prevCode);
            System.exit(1);
        }
 
        String valPrior = dictionary[prevCode];
 
        int step = 0;
        debug("\n=== DECODING LOOP ===");
 
        // Cache bit-shift threshold (same as compression)
        int widthThreshold = 1 << W;
 
        while (!BinaryStdIn.isEmpty()) {
 
            // Increase bit width when crossing threshold
            if (nextCode >= widthThreshold && W < h.maxW) {
                W++;
                widthThreshold = 1 << W;
                debug("Increased W to " + W);
            }
 
            int codeword = BinaryStdIn.readInt(W);
            step++;
            debug("\n--- Step " + step + " ---");
            debug("Read codeword: " + codeword + " (W=" + W + " bits)");
 
            // Check for EOF
            if (codeword == EOF_CODE) {
                debug("Received EOF_CODE, ending decompression");
                break;
            }
 
            // Handle RESET code
            if (resetPolicy && codeword == RESET_CODE) {
                debug("Received RESET_CODE, resetting decoding table");
 
                // Clear dictionary (keep alphabet)
                for (int i = h.alphabetSize; i < dictionary.length; i++) {
                    dictionary[i] = null;
                }
 
                nextCode = initialNextCode;
                W = h.minW;
                widthThreshold = 1 << W;
                debug("Reset complete: nextCode=" + nextCode + ", W=" + W);
 
                // Read first code after reset
                codeword = BinaryStdIn.readInt(W);
                debug("Read post-reset codeword: " + codeword + " (W=" + W + " bits)");
 
                if (codeword == EOF_CODE) {
                    debug("Post-reset code is EOF_CODE, ending");
                    break;
                }
 
                valPrior = dictionary[codeword];
                debug("Decoded: '" + escapeString(valPrior) + "'");
                debug("OUTPUT: '" + escapeString(valPrior) + "'");
                BinaryStdOut.write(valPrior);
 
                continue;
            }
 
            // Decode codeword
            String s;
            if (codeword < nextCode) {
                // Code is in dictionary
                s = dictionary[codeword];
                debug("Codeword " + codeword + " -> '" + escapeString(s) + "'");
            } else if (codeword == nextCode) {
                // Special case: codeword not yet in dictionary
                // This happens when pattern is previous + previous[0]
                // This was the thing fucking me up prior. I'm glad I sorted it out.
                s = valPrior + valPrior.charAt(0);
                debug("Codeword " + codeword + " not in table (special case): '" + escapeString(s) + "'");
            } else {
                System.err.println("Bad compressed code: " + codeword);
                System.exit(1);
                return;
            }
 
            debug("OUTPUT: '" + escapeString(s) + "'");
            BinaryStdOut.write(s);
 
            // Add new pattern to dictionary if not full
            if (nextCode < maxCode) {
                // LRU eviction
                if (lruPolicy && nextCode == maxCode - 1) {
                    debug("LRU: At capacity, need to evict");
                    lruTracker.printState();
                    int lruCode = lruTracker.findLRU();
                    if (lruCode != -1) {
                        debug("EVICTING: code=" + lruCode + " (was '" + escapeString(dictionary[lruCode]) + "')");
                        dictionary[lruCode] = null;
                        lruTracker.remove(lruCode);
                    }
                }
 
                // LFU eviction
                if (lfuPolicy && nextCode == maxCode - 1) {
                    debug("LFU: At capacity, need to evict");
                    lfuTracker.printState();
                    int lfuCode = lfuTracker.findLFU();
                    if (lfuCode != -1) {
                        debug("EVICTING: code=" + lfuCode + " (was '" + escapeString(dictionary[lfuCode]) + "')");
                        dictionary[lfuCode] = null;
                        lfuTracker.remove(lfuCode);
                    }
                }
 
                // Add new pattern: previous + first char of current
                String newEntry = valPrior + s.charAt(0);
                debug("ADDING to table: code " + nextCode + " -> '" + escapeString(newEntry) + "'");
                dictionary[nextCode] = newEntry;
 
                // Track in LRU/LFU
                if (lruPolicy) {
                    lruTracker.use(nextCode);
                }
 
                if (lfuPolicy) {
                    lfuTracker.use(nextCode);
                }
 
                nextCode++;
            } else {
                debug("Table full (nextCode=" + nextCode + " >= maxCode=" + maxCode + ")");
            }
 
            // Update trackers for the codeword we just used
            // Only track non-alphabet codes (alphabet codes are never evicted)
            if (lruPolicy && codeword >= alphabetSize + 1) {
                lruTracker.use(codeword);
            }
 
            if (lfuPolicy && codeword >= alphabetSize + 1) {
                lfuTracker.use(codeword);
            }
 
            valPrior = s;
        }
 
        if (lruPolicy) {
            debug("\nFinal LRU state:");
            lruTracker.printState();
        }
 
        if (lfuPolicy) {
            debug("\nFinal LFU state:");
            lfuTracker.printState();
        }
 
        debug("\n=== DECOMPRESSION COMPLETE ===\n");
        BinaryStdOut.close();
    }
 
    //============================================
    // Header Format
    //============================================
 
    /**
     * Header structure for compressed files
     * Contains all information needed for decompression
     */
    private static class Header {
        int minW;                    // Minimum codeword width
        int maxW;                    // Maximum codeword width
        int policy;                  // Policy code: 0=freeze, 1=reset, 2=lru, 3=lfu
        List<Character> alphabet;    // Alphabet characters
        int alphabetSize;            // Number of alphabet characters
    }
 
    /**
     * Write the header to the compressed output stream.
     * The header contains all information needed to decompress the file:
     * - Codeword width parameters (minW, maxW)
     * - Eviction policy
     * - The complete alphabet
     *
     * Header format (in order):
     * 1. minW (8 bits, up to 256)
     * 2. maxW (8 bits, up to 256)
     * 3. policy code (8 bits): 0=freeze, 1=reset, 2=lru, 3=lfu
     * 4. alphabet size (16 bits): allows up to 65535 symbols
     * 5. alphabet symbols (8 bits each): raw byte value of each character
     *
     * Note: Alphabet uses 8 bits per character (Extended ASCII, 0-255)
     *
     * @param minW     minimum codeword width in bits
     * @param maxW     maximum codeword width in bits
     * @param policy   eviction policy name ("freeze", "reset", "lru", or "lfu")
     * @param alphabet ordered list of single-character symbols
     */
    private static void writeHeader(int minW, int maxW, String policy, List<Character> alphabet) {
        BinaryStdOut.write(minW, 8);
        BinaryStdOut.write(maxW, 8);
 
        // Encode policy as integer
        int policyCode;
        switch (policy) {
            case "freeze": policyCode = 0; break;
            case "reset":  policyCode = 1; break;
            case "lru":    policyCode = 2; break;
            case "lfu":    policyCode = 3; break;
            default:       policyCode = 0; break;  // Default to freeze
        }
        BinaryStdOut.write(policyCode, 8);
 
        // Cache alphabet.size() to avoid multiple method calls
        int alphabetSize = alphabet.size();
        BinaryStdOut.write(alphabetSize, 16);
 
        // Write each symbol (8 bits each for Extended ASCII)
        // Note: No null check needed since alphabet never contains null by design
        // (loadAlphabet only adds char primitives, which auto-box to non-null Characters)
        for (Character symbol : alphabet) {
            BinaryStdOut.write(symbol, 8);
        }
    }
 
    /**
     * Read header from compressed input stream
     *
     * @return Header object containing compression parameters
     */
    private static Header readHeader() {
        Header header = new Header();
 
        header.minW = BinaryStdIn.readInt(8);
        header.maxW = BinaryStdIn.readInt(8);
        header.policy = BinaryStdIn.readInt(8);
 
        int alphabetSize = BinaryStdIn.readInt(16);
        header.alphabetSize = alphabetSize;
 
        // Pre-allocate ArrayList with known size to avoid resizing
        // We know exactly how many characters we'll read, so no need for ArrayList
        // to resize from default capacity (10) up to alphabetSize
        header.alphabet = new ArrayList<>(alphabetSize);
        for (int i = 0; i < alphabetSize; i++) {
            header.alphabet.add(BinaryStdIn.readChar(8));
        }
 
        return header;
    }
}
